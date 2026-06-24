#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reminders.py — NHẮC TRƯỚC MỖI TIẾT HỌC cho bot tương tác (Telegram & Discord).

Bot tương tác vốn BỊ ĐỘNG (chỉ trả lời lệnh). Module này thêm 1 bộ hẹn giờ NHẸ chạy trong
chính tiến trình bot: mỗi vòng kiểm giờ VN, nếu có tiết sắp bắt đầu trong vòng `FAP_REMIND_MINUTES`
phút thì đẩy 1 lời nhắc — MỖI TIẾT CHỈ NHẮC 1 LẦN (nhớ trong `sent`). Đặt FAP_REMIND_MINUTES=0 để tắt.

Lõi `due_reminders()`/`reminder_text()` là THUẦN (không mạng/IO) -> test offline được. `ClassReminder.tick()`
lo phần có mạng: nạp lại TKB trong ngày (cache), tự refresh token ~50' để bot sống lâu, sinh lời nhắc.
"""
import time
from .. import config, fmt
from ..i18n import t
from ..core.api import _vn_now, creds, current_semester
from ..core.schedule import fetch_sessions, sessions_on_day


def lead_minutes():
    """Số phút nhắc trước giờ vào lớp (FAP_REMIND_MINUTES). <=0 / không parse được -> 0 (tắt)."""
    try:
        return max(0, int(str(getattr(config, "REMIND_MINUTES", "30") or "0").strip()))
    except (TypeError, ValueError):
        return 30


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
    """THUẦN: 1 lời nhắc gọn cho chat."""
    rng = start.strftime("%H:%M") + "–" + end.strftime("%H:%M")
    head = (t(f"⏰ Còn {mins}' nữa có tiết:", f"⏰ Class in {mins}':") if mins > 0
            else t("⏰ Tiết bắt đầu ngay:", "⏰ Class starting now:"))
    line = f"🕐 {rng}  {s.get('subjectCode','')}  {fmt.room(s)}"
    gv = s.get("lecturer")
    return head + "\n" + line + (t(f"  ·  GV {gv}", f"  ·  lecturer {gv}") if gv else "")


class ClassReminder:
    """Trạng thái cho bộ nhắc chạy trong bot. Gọi tick() đều đặn (mỗi ~30–60s)."""

    def __init__(self, lead=None):
        self.lead = lead if lead is not None else lead_minutes()
        self.sent = set()            # key tiết đã nhắc trong NGÀY (reset khi sang ngày mới)
        self._sessions = []
        self._day = None
        self._last_load = 0.0
        self._last_refresh = 0.0

    def enabled(self):
        return self.lead > 0

    def _maybe_refresh(self, now_ts, refresh_min=50):
        """Giữ token FAP sống cho bot chạy nền (bot tương tác vốn không tự refresh)."""
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
        now = now or _vn_now()
        self._maybe_refresh(time.time())
        self._maybe_reload(now)
        texts = []
        for start, end, s, mins, k in due_reminders(self._sessions, now, self.lead, self.sent):
            self.sent.add(k)
            texts.append(reminder_text(start, end, s, mins))
        return texts
