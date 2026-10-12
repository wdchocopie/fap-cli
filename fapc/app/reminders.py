#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reminders.py — NHẮC TRƯỚC MỖI TIẾT HỌC cho bot tương tác (Telegram & Discord).

Bot tương tác vốn BỊ ĐỘNG (chỉ trả lời lệnh). Module này thêm 1 bộ hẹn giờ NHẸ chạy trong
chính tiến trình bot: mỗi vòng kiểm giờ VN, nếu có tiết sắp bắt đầu trong vòng `FAP_REMIND_MINUTES`
phút thì đẩy 1 lời nhắc — MỖI TIẾT CHỈ NHẮC 1 LẦN (nhớ trong `sent`). Đặt FAP_REMIND_MINUTES=0 để tắt.

Lõi `due_reminders()`/`reminder_text()` là THUẦN (không mạng/IO) -> test offline được. `ClassReminder.tick()`
lo phần có mạng: nạp lại TKB trong ngày (cache), tự refresh token ~50' để bot sống lâu, sinh lời nhắc.
"""
import hashlib, os, random, threading, time
import requests
from .. import config, fmt
from ..i18n import t
from ..core import paths
from ..core.api import _vn_now, creds, current_semester
from ..core.schedule import fetch_sessions, sessions_on_day

# Gọi thoại Telegram nhắc tiết qua CallMeBot (bật bằng CALLMEBOT_USER) — docs/13-notify.md §8.
CALLMEBOT_URL = "https://api.callmebot.com/start.php"
_CALL_KEEP_S = 2 * 86400       # dấu "đã gọi" cũ hơn 2 ngày bị dọn

# Lệch giờ refresh token lúc KHỞI ĐỘNG — bảng phân dải dùng chung ở fapc/app/_stagger.py.
# reminders chạy TRONG bot (tick ~20–60s) nên KHÔNG ngủ chặn như 2 watcher: chỉ seed mốc, tick dày
# nên lần refresh đầu vẫn tới sớm.
from ._stagger import first_refresh_mark


def _first_refresh_mark(refresh_min, now):
    """Giữ tên cũ cho test/tương thích — nay ủy quyền cho _stagger (dải riêng của reminders)."""
    return first_refresh_mark("reminders", refresh_min, now)


def lead_minutes():
    """Số phút nhắc trước giờ vào lớp (FAP_REMIND_MINUTES). <=0 / không parse được -> 0 (tắt)."""
    try:
        return max(0, int(str(getattr(config, "REMIND_MINUTES", "30") or "0").strip()))
    except (TypeError, ValueError):
        return 0                          # giá trị rác (vd 'off') → TẮT, đúng như docstring hứa


def _key(start, s):
    """Khoá định danh 1 tiết trong NGÀY để chống nhắc trùng (giờ bắt đầu + môn + slot)."""
    return f"{start.strftime('%Y-%m-%dT%H:%M')}|{s.get('subjectCode','')}|{s.get('slot','')}"


def due_reminders(sessions, now, lead, sent):
    """THUẦN: trả [(start, end, session, phút_còn_lại, key)] cho các tiết sắp tới trong cửa sổ
    [now, now+lead] CHƯA nhắc (key không nằm trong `sent`). Tiết đã qua (mins<0) bị bỏ."""
    out = []
    for start, end, s in sessions_on_day(sessions, now.date()):
        k = _key(start, s)
        if k in sent:
            continue
        mins = (start - now).total_seconds() / 60.0
        if 0 <= mins <= lead:
            out.append((start, end, s, int(round(mins)), k))
    return out


def reminder_text(start, end, s, mins):
    """THUẦN: 1 lời nhắc gọn cho chat. Buổi ONLINE có mã Meet -> thêm dòng '🔗 Vào lớp: <link>' riêng ở
    cuối: chạm một cái là vào lớp ngay từ thông báo (Telegram/Discord tự biến URL thành link)."""
    rng = start.strftime("%H:%M") + "–" + end.strftime("%H:%M")
    head = (t(f"⏰ Còn {mins}' nữa có tiết:", f"⏰ Class in {mins}':") if mins > 0
            else t("⏰ Tiết bắt đầu ngay:", "⏰ Class starting now:"))
    line = f"🕐 {rng}  {s.get('subjectCode','')}  {fmt.room(s)}"
    gv = s.get("lecturer")
    line += t(f"  ·  GV {gv}", f"  ·  lecturer {gv}") if gv else ""
    return head + "\n" + fmt.with_meet(line, s, label=t("Vào lớp: ", "Join: "))


def call_text(start, mins):
    """THUẦN: câu đọc trong cuộc gọi. CHỈ có giờ vào lớp — mã môn/phòng/link KHÔNG đi sang dịch vụ bên
    thứ ba (chi tiết đã nằm trong tin nhắc chữ)."""
    at_vi = f"{start.hour} giờ" + (f" {start.minute:02d}" if start.minute else "")
    if mins > 0:
        return t(f"Còn {mins} phút nữa vào lớp, lúc {at_vi}.",
                 f"Class starts in {mins} minute{'s' if mins != 1 else ''}, at {start:%H:%M}.")
    return t(f"Lớp học bắt đầu ngay bây giờ, lúc {at_vi}.", f"Class is starting now, at {start:%H:%M}.")


def call_params(user, start, mins):
    """THUẦN: query của CallMeBot. cc=no: không nhắn bù chữ — tin nhắc chữ của bot đã có rồi."""
    return {"user": user, "text": call_text(start, mins)[:256],
            "lang": t("vi-VN-Standard-A", "en-US-Standard-B"), "rpt": "2", "cc": "no"}


def _claim_call(key, now_ts=None):
    """Chiếm quyền gọi cho 1 tiết, NGUYÊN TỬ giữa các tiến trình (bot Telegram + Discord cùng profile, hay
    bot vừa restart): ai tạo được file đánh dấu (O_EXCL) trước thì gọi, người sau bỏ qua. Tên file = sha1
    của khoá nên không lộ môn/giờ. Dọn dấu cũ hơn _CALL_KEEP_S."""
    d = paths.out("call_marks")
    os.makedirs(d, exist_ok=True)
    now_ts = time.time() if now_ts is None else now_ts
    for name in os.listdir(d):
        p = os.path.join(d, name)
        try:
            if now_ts - os.path.getmtime(p) > _CALL_KEEP_S:
                os.remove(p)
        except OSError:
            pass
    mark = os.path.join(d, hashlib.sha1(key.encode("utf-8")).hexdigest())
    try:
        os.close(os.open(mark, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except FileExistsError:
        return False


def _ring(params, tries=2, gap=10):
    """Gọi API, lỗi thì thử lại 1 lần (dấu đã chiếm nên không lượt nào khác gọi bù). Lỗi CHỈ in HTTP status /
    TÊN lớp lỗi: thông điệp lỗi của requests chứa URL (có username)."""
    for i in range(tries):
        if i:
            time.sleep(gap)
        try:
            r = requests.get(CALLMEBOT_URL, params=params, timeout=90, allow_redirects=False)
        except requests.RequestException as e:
            print(t("  CallMeBot lỗi mạng:", "  CallMeBot network error:"), type(e).__name__)
            continue
        if 200 <= r.status_code < 300:
            return True
        print(t(f"  CallMeBot lỗi: HTTP {r.status_code}", f"  CallMeBot error: HTTP {r.status_code}"))
    return False


def call_reminder(key, start, mins):
    """Gọi thoại Telegram nhắc tiết (CALLMEBOT_USER trống = tắt). Chạy THREAD NỀN: API có thể giữ kết nối tới
    hết cuộc gọi (~30 s) — không được chặn vòng bot (getUpdates, nhắc tiết). Trả True nếu đã phát lệnh gọi."""
    user = str(getattr(config, "CALLMEBOT_USER", None) or "").strip()
    if not user:
        return False
    try:
        if not _claim_call(key):
            return False
    except OSError as e:                     # không ghi được dấu -> KHÔNG gọi (thà thiếu còn hơn gọi trùng)
        print(t("  CallMeBot: không ghi được dấu đã gọi —", "  CallMeBot: cannot write the call mark —"),
              type(e).__name__)
        return False
    threading.Thread(target=_ring, args=(call_params(user, start, mins),), name="fap-call", daemon=True).start()
    return True


class ClassReminder:
    """Trạng thái cho bộ nhắc chạy trong bot. Gọi tick() đều đặn (mỗi ~30–60s)."""

    def __init__(self, lead=None):
        self.lead = lead if lead is not None else lead_minutes()
        self.sent = set()            # key tiết đã nhắc trong NGÀY (reset khi sang ngày mới)
        self._sessions = []
        self._day = None
        self._last_load = 0.0
        self._last_refresh = 0.0     # 0 = CHƯA đặt mốc; _maybe_refresh() sẽ seed lệch (xem _first_refresh_mark)

    def enabled(self):
        return self.lead > 0

    def _maybe_refresh(self, now_ts, refresh_min=50):
        """Giữ token FAP sống cho bot chạy nền (bot tương tác vốn không tự refresh)."""
        if not self._last_refresh:              # tick ĐẦU: seed mốc lệch, đừng refresh ngay cùng lúc với watcher
            self._last_refresh = _first_refresh_mark(refresh_min, now_ts)
        if now_ts - self._last_refresh > refresh_min * 60:
            try:
                from .attendwatch import _refresh_token
                _refresh_token()
            except Exception:        # noqa: BLE001 — refresh best-effort, không làm chết bot
                pass
            self._last_refresh = now_ts    # luôn dời mốc (kể cả fail) -> không spam token endpoint

    def _maybe_reload(self, now, reload_min=180):
        """Nạp TKB của HÔM NAY (cache ~3h, và nạp lại khi sang ngày mới)."""
        now_ts = time.time()
        fresh = self._sessions and self._day == now.date() and (now_ts - self._last_load) < reload_min * 60
        if fresh:
            return
        try:
            token, campus, roll = creds()
            sem = current_semester(token, campus, roll)
            sessions = fetch_sessions(token, campus, roll, sem)
        except SystemExit:           # token hết hạn -> giữ cache cũ, thử lại lượt sau
            return
        except Exception:            # noqa: BLE001 — blip mạng, đừng làm chết bot
            return
        if sessions:
            if self._day != now.date():
                self.sent.clear()    # ngày mới -> quên 'đã nhắc' của hôm qua
            self._sessions, self._day, self._last_load = sessions, now.date(), now_ts

    def tick(self, now=None):
        """1 nhịp: refresh token (định kỳ) + nạp TKB (cache) + trả list lời nhắc CẦN GỬI ngay."""
        if not self.enabled():
            return []
        # _vn_now() là offset-AWARE; giờ bắt đầu tiết (sessions_on_day) là NAIVE → phải strip tz,
        # nếu không `start - now` ném "can't subtract offset-naive and offset-aware datetimes".
        now = (now or _vn_now()).replace(tzinfo=None)
        self._maybe_refresh(time.time())
        self._maybe_reload(now)
        texts = []
        for start, end, s, mins, k in due_reminders(self._sessions, now, self.lead, self.sent):
            self.sent.add(k)
            texts.append(reminder_text(start, end, s, mins))
            try:                                 # gọi thoại (nếu bật): kênh PHỤ — lỗi gì cũng không được nuốt mất tin chữ
                call_reminder(k, start, mins)
            except Exception as e:               # noqa: BLE001 — vd không tạo được thread
                print(t("  CallMeBot lỗi:", "  CallMeBot error:"), type(e).__name__)
        return texts
