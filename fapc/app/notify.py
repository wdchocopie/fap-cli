#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notify.py — Đẩy thông báo lịch học lên kênh chat (Telegram + Discord).

Cấu hình qua .env: TELEGRAM_TOKEN, TELEGRAM_CHAT, DISCORD_WEBHOOK_URL (xem .env.example).

Chạy (từ gốc repo):
    fap notify test                    # gửi tin thử tới các kênh đã cấu hình
    fap notify today|tomorrow|weekly   # lịch học -> kênh
    fap notify attendance|banrisk      # điểm danh / cảnh báo cấm thi -> kênh
    fap notify grades|status|whatif    # điểm / tổng quan / mô phỏng GPA -> kênh

Mọi lệnh (trừ `test`) dùng chung lõi `bot_core.handle()` rồi đẩy kết quả lên kênh đã cấu hình.
"""
import os, sys, time, json, datetime
import requests
from ..core.schedule import sessions_on_day
from ..core import subjects
from ..i18n import t
from .. import config, fmt

_UA = {"User-Agent": "fapc/1.0 (+FAP schedule notifier)"}
_SEEN_NOTIF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "output", "seen_notifications.json")

# ---------- kênh ----------
# Lưu ý: requests.post KHÔNG ném lỗi khi server trả HTTP 4xx/5xx — chỉ ném khi lỗi MẠNG.
# Vì vậy phải KIỂM TRA status code, nếu không sẽ báo "đã gửi" dù chat_id/token/webhook sai.
def _retry_after(r):
    """Số giây Retry-After từ 429 (Telegram: parameters.retry_after; Discord: retry_after/header). Trần 30s."""
    ra = None
    try:
        j = r.json()
        ra = (j.get("parameters") or {}).get("retry_after") if isinstance(j, dict) else None
        if ra is None and isinstance(j, dict):
            ra = j.get("retry_after")
    except ValueError:
        ra = None
    if ra is None:
        ra = r.headers.get("Retry-After")
    try:
        return min(float(ra), 30.0) if ra is not None else None
    except (TypeError, ValueError):
        return None

def _post_retry(url, payload):
    """POST JSON; nếu 429 thì đọc Retry-After, ngủ rồi gửi lại 1 lần (để không rớt tin quan trọng)."""
    r = requests.post(url, json=payload, headers=_UA, timeout=15)
    if r.status_code == 429:
        wait = _retry_after(r) or 2.0
        print(f"  rate-limit 429 — chờ {wait:.1f}s rồi gửi lại…")
        time.sleep(wait)
        r = requests.post(url, json=payload, headers=_UA, timeout=15)
    return r

def _telegram(text):
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT):
        return False
    try:
        r = _post_retry(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                        {"chat_id": config.TELEGRAM_CHAT, "text": text[:4000]})
    except requests.RequestException as e:
        print("  Telegram lỗi mạng · network:", e); return False
    try:
        ok = r.ok and bool(r.json().get("ok"))     # Telegram luôn trả JSON có trường "ok"
    except ValueError:
        ok = r.ok
    if ok:
        return True
    print(f"  Telegram lỗi · error: HTTP {r.status_code} — {str(r.text)[:160]}")
    return False

def _discord(text):
    if not config.DISCORD_WEBHOOK_URL:
        return False
    try:
        r = _post_retry(config.DISCORD_WEBHOOK_URL, {"content": text[:1900]})
    except requests.RequestException as e:
        print("  Discord lỗi mạng · network:", e); return False
    if r.status_code in (200, 204):                 # webhook thành công = 204 (hoặc 200)
        return True
    print(f"  Discord lỗi · error: HTTP {r.status_code} — {str(r.text)[:160]}")
    return False

def push(text):
    """Gửi tới mọi kênh đã cấu hình. Trả danh sách kênh đã gửi."""
    sent = []
    if _telegram(text): sent.append("Telegram")
    if _discord(text):  sent.append("Discord")
    return sent

# ---------- đẩy thông báo MỚI (dedupe theo id) ----------
def _load_seen():
    """set id đã thấy; None nếu CHƯA hề ghi mốc (file vắng) — khác 'đã ghi mốc nhưng rỗng' (set())."""
    try:
        with open(_SEEN_NOTIF, encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return None
    except (ValueError, OSError):
        # File HỎNG -> cô lập .corrupt + cảnh báo; trả None để coi như first_run (ghi mốc, KHÔNG dội cả cửa sổ).
        try: os.replace(_SEEN_NOTIF, _SEEN_NOTIF + ".corrupt")
        except OSError: pass
        print(t("⚠️ seen_notifications.json hỏng → thiết lập lại mốc; lượt này KHÔNG dội thông báo cũ.",
                "⚠️ seen_notifications.json corrupt → rebaselining; this round will NOT replay old notifications."))
        return None

def _save_seen(ids):
    os.makedirs(os.path.dirname(_SEEN_NOTIF), exist_ok=True)
    tmp = _SEEN_NOTIF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(ids), f)
    os.replace(tmp, _SEEN_NOTIF)

def push_new_notifications():
    """Đẩy CHỈ thông báo MỚI (id chưa từng thấy) lên kênh. Lần đầu chỉ ghi mốc, KHÔNG dội cả danh sách."""
    from ..core.api import creds
    from ..core.extras import fetch_notifications, _notif_line
    token, campus, roll = creds()
    rows = fetch_notifications(token, campus, roll)
    ids = [str(n.get("id")) for n in rows if n.get("id") is not None]
    loaded = _load_seen()
    first_run = loaded is None                  # CHƯA ghi mốc lần nào (file vắng) — khác mốc-rỗng
    seen = loaded or set()
    new = [n for n in rows if n.get("id") is not None and str(n.get("id")) not in seen]  # id rỗng -> KHÔNG coi là mới
    if not rows and not first_run:              # phản hồi rỗng tạm thời SAU baseline -> ĐỪNG xoá mốc, dò lại lượt sau
        print(t("(Không lấy được thông báo — bỏ qua lượt này.)", "(Couldn't fetch notifications — skipping this round.)")); return
    _save_seen(ids)                             # mốc = id hiện có trên server (tự bó theo cửa sổ server trả)
    if first_run:
        print(t(f"👀 Ghi mốc {len(ids)} thông báo. Lần sau chỉ báo cái mới.",
                f"👀 Baselined {len(ids)} notifications. Only new ones from now on.")); return
    if not new:
        print(t("Không có thông báo mới.", "No new notifications.")); return
    new.sort(key=lambda n: str(n.get("entryDate") or ""))
    msg = fmt.header("🔔", t("Thông báo MỚI", "New notifications"), str(len(new))) + "\n" + "\n".join(_notif_line(n) for n in new)
    print(msg)
    sent = push(msg)
    print(t("→ Đã gửi tới:", "→ Sent to:"), sent or t("(chưa cấu hình kênh — sửa .env)", "(no channel — edit .env)"))

# ---------- nội dung ----------
def _day_digest(sessions, day):
    items = sessions_on_day(sessions, day)         # [(start, end, session), ...] đã sort
    title = f"{fmt.weekday(day)} · {day.strftime('%d/%m/%Y')}"
    if not items:
        return fmt.header("📅", title) + "\n" + t("🎉 Hôm đó không có buổi học", "🎉 No classes that day")
    lines = [fmt.header("📅", title, t(f"{len(items)} buổi", f"{len(items)} sessions"))]
    for start, end, s in items:
        rng = start.strftime("%H:%M") + "–" + end.strftime("%H:%M")
        lines.append(f"🕐 {rng}  {subjects.label(s.get('subjectCode',''))}  {fmt.room(s)}")
    return "\n".join(lines)

def _week_digest(sessions, today):
    """Tóm tắt lịch cả tuần (T2..CN) chứa 'today'."""
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    title = t(f"Tuần {monday.strftime('%d/%m')}–{sunday.strftime('%d/%m')}",
              f"Week {monday.strftime('%d/%m')}–{sunday.strftime('%d/%m')}")
    lines, total = [fmt.header("📆", title)], 0
    for i in range(7):
        d = monday + datetime.timedelta(days=i)
        day_items = sessions_on_day(sessions, d)
        if not day_items:
            continue
        total += len(day_items)
        lines.append(f"\n📌 {fmt.weekday(d)} · {d.strftime('%d/%m')}")
        for start, end, s in day_items:
            lines.append(f"   🕐 {start.strftime('%H:%M')}  {subjects.label(s.get('subjectCode',''))}  {fmt.room(s)}")
    if total == 0:
        lines.append(t("🎉 Tuần này không có buổi học", "🎉 No classes this week"))
    return "\n".join(lines)

def run(cmd="test"):
    if cmd == "test":
        sent = push(t("✅ fap-cli: kênh thông báo hoạt động.", "✅ fap-cli: notification channels work."))
        print(t("Đã gửi tới:", "Sent to:"),
              sent or t("(chưa cấu hình kênh nào — sửa .env)", "(no channel configured — edit .env)"))
        return
    # Mọi lệnh khác đi chung lõi bot_core.handle() rồi đẩy lên kênh.
    # Import trễ để tránh import vòng (bot_core import _day_digest/_week_digest từ notify).
    from .bot_core import handle, COMMANDS
    parts = str(cmd).split()
    name = parts[0] if parts else "today"            # 'weekly' giờ là lệnh thật (recap), KHÔNG còn alias 'week'
    if name == "notifications":                 # đẩy dedupe (chỉ cái MỚI), khác các view tĩnh
        return push_new_notifications()
    if name == "help" or name not in COMMANDS:
        print(t("Lệnh notify không rõ. Dùng: test | today | tomorrow | weekly | attendance | banrisk | grades | grades-detail | status | whatif [điểm] | exams | gpa | notifications | all",
                "Unknown notify command. Use: test | today | tomorrow | weekly | attendance | banrisk | grades | grades-detail | status | whatif [mark] | exams | gpa | notifications | all"))
        return
    arg = parts[1] if len(parts) > 1 else None
    msg = handle(name, arg)
    print(msg)
    sent = push(msg)
    print(t("→ Đã gửi tới:", "→ Sent to:"),
          sent or t("(chưa cấu hình kênh — sửa .env)", "(no channel — edit .env)"))

def main():
    run(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "test")

if __name__ == "__main__":
    main()
