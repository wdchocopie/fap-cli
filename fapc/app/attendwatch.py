#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attendwatch.py — Theo dõi & báo khi có buổi VỪA ĐƯỢC ĐIỂM DANH (near real-time).

    fap watch-attendance              # 1 lần: dò thay đổi -> báo lên kênh -> thoát (cho cron)
    fap watch-attendance loop [phút]  # chạy nền, dò mỗi <phút> (mặc định 15), 06:00–21:00
    fap watch-attendance --absent-only        # CHỈ báo buổi VẮNG/MUỘN (đỡ spam "Có mặt")
    fap watch-attendance loop 15 --absent-only

CHỐNG SPAM: mỗi buổi chỉ báo ĐÚNG 1 LẦN (nhớ trong state), im lặng khi không có gì mới.
Đặt FAP_WATCH_ABSENT_ONLY=1 trong .env để mặc định chỉ-báo-vắng (vẫn ghi nhận đủ để không báo lại).

CÁCH HOẠT ĐỘNG: FAP không đẩy (webhook) cho mình → phải POLL. Mỗi buổi trong getCourseAttendance
có `attendanceStatus` = "Future" trước giờ, đổi thành "Present"/"Absent"... khi giảng viên điểm danh.
So với lần trước (theo `scheduleID`) để phát hiện buổi MỚI được ghi nhận. Độ trễ = khoảng cách 2 lần dò.

RẺ với server: dò GetStudentAttendances (1 lời gọi); chỉ tải chi tiết môn nào có số buổi tăng.
Trạng thái lưu ở output/attendance_state.json (đã .gitignore).
"""
import os, sys, json, time
from ..core.api import creds, current_semester, call, as_list, _vn_now, _err_code
from ..core.attendance import fetch as fetch_agg          # GetStudentAttendances
from .notify import push
from ..i18n import t
from .. import config, fmt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(_ROOT, "output", "attendance_state.json")

# Ngày & nhãn trạng thái dùng chung từ fmt (giữ tên _fmt_date cho test cũ).
_fmt_date = fmt.fmt_date

def _recorded(rec):
    """True nếu buổi đã được ghi nhận điểm danh (khác 'Future'/rỗng)."""
    st = str(rec.get("attendanceStatus", "")).strip().lower()
    return st not in ("", "future", "not yet", "notyet", "none")

def _is_present(rec):
    return str(rec.get("attendanceStatus", "")).strip().lower() == "present"

def _to_push(events, absent_only):
    """Lọc buổi cần GỬI: absent_only -> chỉ buổi KHÔNG phải 'Present' (vắng/muộn)."""
    return [e for e in events if not _is_present(e[1])] if absent_only else list(events)

def _absent_only_default():
    return str(getattr(config, "WATCH_ABSENT_ONLY", "") or "").strip().lower() in ("1", "true", "yes", "on")

def _course_detail(token, campus, roll, sem, subj, group):
    """Trả list buổi, hoặc None nếu LẤY HỎNG (mạng/token/checksum) — để compute KHÔNG dời mốc & thử lại sau."""
    http, data = call("getCourseAttendance",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem),
         ("ClassName", group), ("SubjectCode", subj), ("Authen", token)], roll, campus)
    if http is None or _err_code(data) == "201":   # blip / token hết hạn / lệch checksum -> THẤT BẠI, khác "rỗng"
        return None
    return as_list(data)

def compute(subjects, detail_fn, state):
    """Lõi THUẦN (không mạng/IO) — test offline được.
    subjects: list GetStudentAttendances; detail_fn(subj, group) -> list buổi; state: dict cũ.
    Trả (events[(subj, record)], new_state, first_run)."""
    first_run = not state
    new_state, events = {}, []
    for s in subjects:
        subj, group = s.get("subjectCode"), s.get("groupName")
        taken = s.get("numberOfTakenAttendances")
        prev = state.get(subj, {})
        # Cổng rẻ: số buổi đã điểm danh không đổi -> khỏi tải chi tiết môn này.
        if (not first_run) and subj in state and prev.get("taken") == taken:
            new_state[subj] = prev
            continue
        seen = set(prev.get("seen", []))
        detail = detail_fn(subj, group)
        if detail is None:                       # lấy chi tiết HỎNG -> GIỮ nguyên mốc cũ, dò lại lượt sau
            if subj in state:
                new_state[subj] = prev
            continue
        recorded = [r for r in detail if _recorded(r)]
        rec_ids = [str(r.get("scheduleID")) for r in recorded]
        if not first_run:
            events += [(subj, r) for r in recorded if str(r.get("scheduleID")) not in seen]
        new_state[subj] = {"taken": taken, "seen": rec_ids, "group": group}
    return events, new_state, first_run

def _load_state():
    if not os.path.exists(STATE):
        return {}
    try:
        with open(STATE, encoding="utf-8") as f:          # ĐÓNG handle trước os.replace (Windows không rename file đang mở)
            return json.load(f)
    except (ValueError, OSError):
        # State HỎNG -> giữ lại làm .corrupt + CẢNH BÁO RÕ (đừng im lặng coi là first_run).
        try: os.replace(STATE, STATE + ".corrupt")
        except OSError: pass
        print(t("⚠️ attendance_state.json hỏng → thiết lập lại baseline; lượt này có thể bỏ sót buổi đã ghi.",
                "⚠️ attendance_state.json corrupt → rebaselining; this round may miss already-recorded sessions."))
        return {}

def _save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"                                  # ghi ATOMIC: tmp rồi replace -> không để JSON dở
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)

def _event_line(subj, r):
    return (f"• {subj} · {_fmt_date(r.get('date'))} · slot {r.get('slot')}\n"
            f"   {fmt.room(r)} → {fmt.status_label(r.get('attendanceStatus'))}")

def poll(notify=True, absent_only=None):
    """1 lượt dò. Trả số buổi mới phát hiện.
    absent_only=True -> chỉ GỬI buổi vắng/muộn (vẫn ghi nhận hết để KHÔNG báo lại). None = theo .env."""
    if absent_only is None:
        absent_only = _absent_only_default()
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    subjects = fetch_agg(token, campus, roll, sem)
    if not subjects:
        # Token hết hạn / lỗi tạm thời -> KHÔNG ghi đè state (tránh xoá mốc, nuốt buổi mới).
        print(t("(Không lấy được điểm danh — token hết hạn? Bỏ qua lượt này; chạy 'fap refresh'.)",
                "(Couldn't fetch attendance — token expired? Skipping; run 'fap refresh'.)"))
        return 0
    detail_fn = lambda subj, group: _course_detail(token, campus, roll, sem, subj, group)
    events, new_state, first_run = compute(subjects, detail_fn, _load_state())
    _save_state(new_state)                       # ghi nhận MỌI buổi mới -> không bao giờ báo lại
    if first_run:
        print(t(f"👀 Bắt đầu theo dõi điểm danh ({len(subjects)} môn). Sẽ báo khi có buổi mới được điểm danh.",
                f"👀 Now watching attendance ({len(subjects)} subjects). You'll get a ping on each new record."))
        return 0
    if not events:
        print(t("Chưa có điểm danh mới.", "No new attendance.")); return 0
    events.sort(key=lambda e: str(e[1].get("date")))
    # Console LUÔN hiện mọi buổi mới (kể cả Có mặt) để bạn nắm được:
    print(fmt.header("🔔", t("Buổi mới được điểm danh:", "Newly recorded:")) + "\n"
          + "\n".join(_event_line(s, r) for s, r in events))
    to_push = _to_push(events, absent_only)
    if not to_push:
        print(t("(Tất cả đều Có mặt — KHÔNG gửi thông báo, đỡ làm phiền.)",
                "(All Present — no push, to avoid noise.)"))
        return len(events)
    if notify:
        emoji = "⚠️" if absent_only else "🔔"
        head = t("Bị đánh VẮNG / MUỘN!", "Marked Absent / Late!") if absent_only else t("Vừa điểm danh!", "Just recorded!")
        msg = fmt.header(emoji, head) + "\n" + "\n".join(_event_line(s, r) for s, r in to_push)
        sent = push(msg)
        print(t("→ Đã gửi tới:", "→ Sent to:"), sent or t("(chưa cấu hình kênh — sửa .env)", "(no channel — edit .env)"))
    return len(events)

def _refresh_token():
    """Tự làm mới FAP token (headless) để service sống lâu. Best-effort, không làm chết loop."""
    try:
        from ..core.auth import refresh_tokens
        refresh_tokens()
        return True
    except SystemExit as e:
        print(t("  refresh thất bại (sẽ thử lại sau): ", "  refresh failed (will retry): "), e)
    except Exception as e:                            # noqa: BLE001
        print("  refresh lỗi · error:", e)
    return False

def loop(interval_min=15, absent_only=None, refresh_min=50):
    try: interval_min = int(interval_min)
    except (TypeError, ValueError):
        print(t("Số phút không hợp lệ, dùng 15.", "Invalid minutes, using 15.")); interval_min = 15
    interval_min = max(interval_min, 5)              # tối thiểu 5 phút — nhẹ tay với server
    on = absent_only if absent_only is not None else _absent_only_default()
    mode = t(" [chỉ báo vắng]", " [absent-only]") if on else ""
    print(t(f"👀 Theo dõi điểm danh mỗi {interval_min}' (06:00–21:00 giờ VN){mode}; tự refresh token ~{refresh_min}'. Ctrl+C để dừng.",
            f"👀 Watching attendance every {interval_min}m (06:00–21:00 VN){mode}; auto token-refresh ~{refresh_min}m. Ctrl+C to stop."))
    last_refresh = 0.0
    while True:
        if 6 <= _vn_now().hour <= 21:
            if time.time() - last_refresh > refresh_min * 60:   # giữ token sống cho service chạy nền
                _refresh_token()
                last_refresh = time.time()       # LUÔN dời mốc dù refresh fail -> không spam /connect/token mỗi vòng
            try:
                poll(notify=True, absent_only=absent_only)
            except SystemExit as e:                  # token hết hạn... — đừng chết, thử lại lượt sau
                print(t("  (bỏ qua lượt này) ", "  (skipping this round) "), e)
            except Exception as e:                    # noqa: BLE001
                print("  lỗi · error:", e)
        time.sleep(interval_min * 60)

def run(args=None):
    args = args or []
    _AO = ("absent-only", "absentonly", "absent")
    flag = any(str(a).lstrip("-").lower() in _AO for a in args)
    rest = [a for a in args if str(a).lstrip("-").lower() not in _AO]
    ao = True if flag else None         # có cờ -> bật; không cờ -> theo .env (FAP_WATCH_ABSENT_ONLY)
    if rest and str(rest[0]).lstrip("-").lower() == "loop":
        loop(rest[1] if len(rest) > 1 else 15, absent_only=ao)
    else:
        poll(notify=True, absent_only=ao)

def main():
    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        print("\nĐã dừng.")
        sys.exit(0)

if __name__ == "__main__":
    main()
