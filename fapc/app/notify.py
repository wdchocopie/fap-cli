#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notify.py — Đẩy thông báo lịch học lên kênh chat (Telegram + Discord).

Cấu hình qua .env: TELEGRAM_TOKEN, TELEGRAM_CHAT, DISCORD_WEBHOOK_URL (xem .env.example).

Chạy (từ gốc repo):
    fap notify test                    # gửi tin thử tới các kênh đã cấu hình
    fap notify today|tomorrow|weekly   # lịch học -> kênh
    fap notify semester [weeks]        # lịch cả kỳ (mẫu lặp / từng tuần) -> kênh
    fap notify attendance|banrisk      # điểm danh / cảnh báo cấm thi -> kênh
    fap notify grades|status|whatif    # điểm / tổng quan / mô phỏng GPA -> kênh
    fap notify grades-detail IAP491    # tham số NHIỀU TỪ được giữ nguyên (split(None, 1))

Mọi lệnh (trừ `test`) dùng chung lõi `bot_core.handle()` rồi đẩy kết quả lên kênh đã cấu hình;
allowlist = `bot_core.COMMANDS` nên lệnh mới tự dùng được, không phải sửa file này.
"""
import os, sys, time, json, datetime
import requests
from ..core.schedule import sessions_on_day
from ..core.attendance import att_tail
from ..core import subjects, paths
from ..i18n import t
from .. import config, fmt

_UA = {"User-Agent": "fapc/1.0 (+FAP schedule notifier)"}
_SEEN_NOTIF = paths.out("seen_notifications.json")

# Trần ký tự MỘT tin nhắn của từng kênh (trần thật: Telegram 4096 / Discord 2000 — chừa biên an toàn).
# Tin dài hơn được CẮT THÀNH NHIỀU MẨU (fmt.chunks) rồi gửi lần lượt — KHÔNG cắt cụt làm mất chữ.
TELEGRAM_LIMIT = 4000
DISCORD_LIMIT  = 1900
_GAP = 0.4      # giây nghỉ giữa 2 mẩu — nhẹ tay với API (số mẩu rất nhỏ: 2–3)

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

def _partial(chan, done, total):
    """Cảnh báo GỬI DỞ: mẩu đầu đã tới nơi nhưng mẩu sau hỏng -> người đọc đang thiếu chữ."""
    if done:
        print(t(f"  ⚠️ {chan}: mới gửi {done}/{total} mẩu — phần còn lại CHƯA tới nơi.",
                f"  ⚠️ {chan}: only {done}/{total} chunks sent — the rest did NOT arrive."))
    return False                                    # gửi dở KHÔNG bao giờ tính là thành công

def _telegram(text):
    """Gửi tới Telegram, cắt thành NHIỀU tin ≤ TELEGRAM_LIMIT. True chỉ khi MỌI mẩu đã tới nơi."""
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT):
        return False
    parts = fmt.chunks(text, TELEGRAM_LIMIT)
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    for i, part in enumerate(parts):
        if i:
            time.sleep(_GAP)
        try:
            r = _post_retry(url, {"chat_id": config.TELEGRAM_CHAT, "text": part})
        except requests.RequestException as e:
            print("  Telegram lỗi mạng · network:", e); return _partial("Telegram", i, len(parts))
        try:
            ok = r.ok and bool(r.json().get("ok"))  # Telegram luôn trả JSON có trường "ok"
        except ValueError:
            ok = r.ok
        if not ok:
            print(f"  Telegram lỗi · error: HTTP {r.status_code} — {str(r.text)[:160]}")
            return _partial("Telegram", i, len(parts))
    return True

def _discord(text):
    """Gửi tới webhook Discord, cắt thành NHIỀU tin ≤ DISCORD_LIMIT. True chỉ khi MỌI mẩu đã tới nơi."""
    if not config.DISCORD_WEBHOOK_URL:
        return False
    parts = fmt.chunks(text, DISCORD_LIMIT)
    for i, part in enumerate(parts):
        if i:
            time.sleep(_GAP)
        try:
            # allowed_mentions parse=[]: nội dung đến từ FAP (tin tức, tên GV, link lớp…) — một chuỗi server
            # chứa '@everyone'/'@here' không được phép ping cả server Discord. Bot không bao giờ cần mention.
            r = _post_retry(config.DISCORD_WEBHOOK_URL, {"content": part, "allowed_mentions": {"parse": []}})
        except requests.RequestException as e:
            print("  Discord lỗi mạng · network:", e); return _partial("Discord", i, len(parts))
        if r.status_code not in (200, 204):          # webhook thành công = 204 (hoặc 200)
            print(f"  Discord lỗi · error: HTTP {r.status_code} — {str(r.text)[:160]}")
            return _partial("Discord", i, len(parts))
    return True

def push(text):
    """Gửi tới mọi kênh đã cấu hình. Trả danh sách kênh đã gửi ĐẦY ĐỦ (kênh gửi dở KHÔNG được liệt kê)."""
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
    paths.ensure_dir(_SEEN_NOTIF)                   # thư mục profile có thể chưa tồn tại
    tmp = _SEEN_NOTIF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(ids), f)
    os.replace(tmp, _SEEN_NOTIF)
    # 0600 như auth/gcal: dưới chế độ nhiều profile, đây là lịch sử thông báo của NGƯỜI KHÁC.
    try: os.chmod(_SEEN_NOTIF, 0o600)
    except OSError: pass

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
        # with_meet: buổi online -> link Meet ở DÒNG RIÊNG ngay dưới (vẫn 1 phần tử/buổi)
        lines.append(fmt.with_meet(f"🕐 {rng}  {subjects.label(s.get('subjectCode',''))}  {fmt.room(s)}"
                                   f"{att_tail(s)}", s, indent="   "))   # ✅/❌ = đã điểm danh (buổi đã qua)
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
            lines.append(fmt.with_meet(
                f"   🕐 {start.strftime('%H:%M')}  {subjects.label(s.get('subjectCode',''))}  {fmt.room(s)}"
                f"{att_tail(s)}", s, indent="      "))
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
    # split(None, 1): TÁCH ĐÚNG 1 LẦN -> tham số nhiều từ còn nguyên vẹn
    # (`notify news học bổng` trước đây mất chữ "bổng").
    parts = str(cmd).split(None, 1)
    name = parts[0] if parts else "today"            # 'weekly' giờ là lệnh thật (recap), KHÔNG còn alias 'week'
    arg = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    if name == "notifications":                 # đẩy dedupe (chỉ cái MỚI), khác các view tĩnh
        return push_new_notifications()
    if name == "help" or name not in COMMANDS:
        # Danh sách SINH TỪ COMMANDS (COMMAND_INFO) -> không thể lệch khi thêm lệnh mới.
        avail = " | ".join(["test"] + [c for c in COMMANDS if c != "help"])
        print(t(f"Lệnh notify không rõ. Dùng: {avail}", f"Unknown notify command. Use: {avail}"))
        return
    msg = handle(name, arg)
    print(msg)
    sent = push(msg)
    print(t("→ Đã gửi tới:", "→ Sent to:"),
          sent or t("(chưa cấu hình kênh — sửa .env)", "(no channel — edit .env)"))

def main():
    run(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "test")

if __name__ == "__main__":
    main()
