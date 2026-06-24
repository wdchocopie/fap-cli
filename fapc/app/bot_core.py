#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bot_core.py — lõi xử lý lệnh chung cho bot Telegram & Discord.

handle(cmd, arg) -> chuỗi trả lời (text). MỌI lời gọi API xảy ra ở đây — bot chạy nền sẽ
gọi live theo từng lệnh. Tái dùng các hàm fetch + digest sẵn có; định dạng GỌN cho chat.
"""
import datetime
from ..core.api import creds, current_semester, _vn_now
from ..core.schedule import fetch_sessions
from .notify import _day_digest, _week_digest
from ..core.grades import fetch_marks, _gpa, term_gpa, detail_text
from ..core.courses import courses_text
from ..core import subjects
from ..core.attendance import fetch as fetch_att, _at_risk
from ..core.whatif import _split, needed_average, WHATIF_STEPS, MARK_MAX
from ..core.extras import exams_text, notifications_text, profile_text, applications_text, countdown_text
from ..core.transcript import gpa_text, trend_text, credits_overview, fetch as _fetch_transcript
from ..core.conduct import conduct_text
from ..i18n import t
from .. import fmt

# NGUỒN DUY NHẤT cho danh sách lệnh · single source of truth for the command list.
# (tên, mô tả VI, mô tả EN) — dùng cho COMMANDS + menu Telegram (setMyCommands) + slash Discord.
COMMAND_INFO = [
    ("today",         "Lịch học hôm nay",          "Today's schedule"),
    ("tomorrow",      "Lịch học ngày mai",         "Tomorrow's schedule"),
    ("week",          "Lịch học cả tuần",          "This week's schedule"),
    ("weekly",        "Tổng kết tuần (lịch+điểm danh+điểm)", "Weekly recap (schedule+attendance+grades)"),
    ("grades",        "Điểm + GPA tạm tính",       "Grades + provisional GPA"),
    ("grades-detail", "Điểm thành phần từng môn",  "Per-subject component marks"),
    ("courses",       "Lớp đang học (GV/phòng)",   "My classes (lecturer/room)"),
    ("attendance",    "Tỉ lệ điểm danh",           "Attendance percentage"),
    ("banrisk",       "Cảnh báo nguy cơ cấm thi",  "Exam-ban risk (<80%)"),
    ("whatif",        "Mô phỏng GPA (kèm điểm)",   "GPA what-if (optional mark)"),
    ("status",        "Tổng quan nhanh",           "Quick overview"),
    ("exams",         "Lịch thi",                  "Exam schedule"),
    ("exam-countdown","Đếm ngược ngày thi",        "Days until each exam"),
    ("gpa",           "GPA tích lũy (tín chỉ)",    "Cumulative credit GPA"),
    ("gpa-trend",     "GPA theo kỳ + xu hướng",    "Per-term GPA trend"),
    ("credits",       "Tiến độ tín chỉ tốt nghiệp","Credit progress"),
    ("conduct",       "Điểm rèn luyện/phong trào", "Conduct / movement points"),
    ("notifications", "Thông báo của trường",      "School notifications"),
    ("profile",       "Hồ sơ sinh viên",           "Student profile"),
    ("applications",  "Đơn từ + trạng thái xử lý", "Applications + status"),
    ("all",           "Tất cả trong một tin",      "Everything in one message"),
    ("help",          "Danh sách lệnh",            "List all commands"),
]
# Lệnh hỗ trợ (không kèm dấu / hay !) · supported commands (without leading / or !)
COMMANDS = [name for name, _, _ in COMMAND_INFO]

def menu_commands():
    """[(tên, mô tả)] để đăng ký menu lệnh tự-gợi-ý (Telegram setMyCommands / slash Discord).
    Telegram chỉ cho phép [a-z0-9_] trong tên lệnh -> đổi '-' thành '_' (handle() chuẩn hoá lại)."""
    return [(name.replace("-", "_"), t(vi, en)) for name, vi, en in COMMAND_INFO]

def help_text():
    return fmt.header("🤖", "FAP bot") + "\n" + t(
        "📅 /today · /tomorrow · /week — lịch học\n"
        "📊 /grades — điểm + GPA tạm tính\n"
        "🟢 /attendance — điểm danh\n"
        "⚠️ /banrisk — nguy cơ cấm thi\n"
        "🎯 /whatif [điểm] — mô phỏng GPA\n"
        "📝 /exams — lịch thi\n"
        "🧮 /grades-detail — điểm thành phần\n"
        "📈 /gpa — GPA tích lũy (tín chỉ)\n"
        "🔔 /notifications — thông báo · 📄 /applications — đơn từ\n"
        "👤 /profile — hồ sơ\n"
        "📋 /status — tổng quan · 📚 /all — tất cả\n"
        "❓ /help — trợ giúp",
        "📅 /today · /tomorrow · /week — schedule\n"
        "📊 /grades — grades + provisional GPA\n"
        "🟢 /attendance — attendance\n"
        "⚠️ /banrisk — exam-ban risk\n"
        "🎯 /whatif [mark] — GPA what-if\n"
        "📝 /exams — exam schedule\n"
        "🧮 /grades-detail — component marks\n"
        "📈 /gpa — cumulative GPA (credit)\n"
        "🔔 /notifications — notifications · 📄 /applications — applications\n"
        "👤 /profile — student profile\n"
        "📋 /status — overview · 📚 /all — everything\n"
        "❓ /help — help")

def _grades_text(token, campus, roll, sem, rows=None):
    if rows is None:
        rows = fetch_marks(token, campus, roll, sem)
    if not rows:
        return t("📊 Chưa có dữ liệu điểm.", "📊 No grades yet.")
    lines = [fmt.header("📊", t(f"Điểm · {sem}", f"Grades · {sem}"), t(f"{len(rows)} môn", f"{len(rows)} subjects"))]
    for r in rows:
        mk = r.get("averageMark") if fmt.has_mark(r) else fmt.gpa_val(None)
        st = str(r.get("status", ""))
        icon = "✅" if ("pass" in st.lower() and "not" not in st.lower()) else "⏳"
        lines.append(f"• {subjects.label(r.get('subjectCode',''))} — {mk}  {icon} {st}")
    g, weighted = term_gpa(rows)
    gv = fmt.gpa_val(g)
    lines.append("\n" + (t(f"🎯 GPA tạm tính (tín chỉ): {gv}", f"🎯 Provisional GPA (credit): {gv}") if weighted
                         else t(f"🎯 GPA tạm tính: {gv}", f"🎯 Provisional GPA: {gv}")))
    return "\n".join(lines)

def _att_text(token, campus, roll, sem, rows=None):
    if rows is None:
        rows = fetch_att(token, campus, roll, sem)
    if not rows:
        return t("🟢 Chưa có dữ liệu điểm danh.", "🟢 No attendance yet.")
    lines = [fmt.header("🟢", t(f"Điểm danh · {sem}", f"Attendance · {sem}"))]
    for r in rows:
        warn = " ⚠️" if _at_risk(r) else ""
        taken, total = r.get("numberOfTakenAttendances"), r.get("numberOfAttendances")
        cnt = f"  ({taken}/{total})" if taken is not None and total is not None else ""
        lines.append(f"• {subjects.label(r.get('subjectCode',''))} — {r.get('attendance','')}%{warn}{cnt}")
    return "\n".join(lines)

def _banrisk_text(token, campus, roll, sem, rows=None):
    if rows is None:
        rows = fetch_att(token, campus, roll, sem)
    risk = [r for r in rows if _at_risk(r)]
    if not risk:
        return t("✅ Không môn nào nguy cơ cấm thi (≥80%).", "✅ No exam-ban risk (≥80%).")
    lines = [fmt.header("⚠️", t("Nguy cơ cấm thi (<80%)", "Exam-ban risk (<80%)"))]
    for r in risk:
        lines.append(f"• {subjects.label(r.get('subjectCode',''))} — {r.get('attendance','')}%")
    return "\n".join(lines)

def _whatif_text(token, campus, roll, sem, arg):
    rows = fetch_marks(token, campus, roll, sem)
    graded, sg, remaining = _split(rows)
    n_total = len(graded) + remaining
    if n_total == 0:
        return t("Không có môn nào trong kỳ.", "No subjects this term.")
    head = fmt.header("🎯", t(f"Mô phỏng GPA · {sem}", f"GPA what-if · {sem}"),
                      t(f"{len(graded)} có điểm / {remaining} chưa", f"{len(graded)} graded / {remaining} left"))
    note = t("(xấp xỉ TB cộng, thang 0–10)", "(approx unweighted mean, 0–10)")
    if remaining == 0:
        return head + "\n" + t("Đã chốt GPA kỳ.", "Term GPA is final.")
    tgt = None
    if arg:
        try: tgt = float(str(arg).replace(",", "."))
        except ValueError: tgt = None
    if tgt is None:
        warn = t(f'(không đọc được "{arg}")\n', f'(could not parse "{arg}")\n') if arg else ""
        body = "\n".join(f"   • đạt {m}/10 → GPA ≈ {round((sg + m * remaining) / n_total, 2)}" for m in WHATIF_STEPS)
        return head + "\n" + warn + t("Nếu các môn còn lại:", "If remaining subjects average:") + "\n" + body + "\n" + note
    need = needed_average(tgt, sg, n_total, remaining)
    if need > MARK_MAX:
        tail = t(f"cần TB {round(need,2)} → vượt 10, không khả thi.", f"need {round(need,2)} → above 10, not feasible.")
    elif need <= 0:
        tail = t("đã chắc chắn đạt (kể cả 0đ phần còn lại).", "already guaranteed.")
    else:
        tail = t(f"cần TB {round(need,2)}/10 trên {remaining} môn còn lại.", f"need avg {round(need,2)}/10 on {remaining} remaining.")
    return head + "\n" + t(f"🎯 Để GPA {round(tgt,2)}: ", f"🎯 For GPA {round(tgt,2)}: ") + tail + "\n" + note

def _status_text(token, campus, roll, sem):
    sessions = fetch_sessions(token, campus, roll, sem)
    parts = [_day_digest(sessions, _vn_now().date())]
    g = fmt.gpa_val(_gpa(fetch_marks(token, campus, roll, sem)))
    parts.append(t(f"🎯 GPA tạm tính: {g}", f"🎯 Provisional GPA: {g}"))
    risk = [r.get("subjectCode", "") for r in fetch_att(token, campus, roll, sem) if _at_risk(r)]
    parts.append(t("⚠️ Nguy cơ cấm thi: ", "⚠️ Ban risk: ") + ", ".join(risk) if risk
                 else t("✅ Chuyên cần ổn (≥80%)", "✅ Attendance OK (≥80%)"))
    return "\n\n".join(parts)

def weekly_text(token, campus, roll, sem):
    """Recap TUẦN trong 1 tin: lịch tuần + điểm danh + cảnh báo cấm thi + điểm hiện tại.
    Lấy sessions/att/marks ĐÚNG 1 LẦN rồi chia sẻ (không gọi trùng endpoint)."""
    sessions = fetch_sessions(token, campus, roll, sem)
    att = fetch_att(token, campus, roll, sem)
    marks = fetch_marks(token, campus, roll, sem)
    today = _vn_now().date()
    parts = [
        _week_digest(sessions, today),
        _att_text(token, campus, roll, sem, rows=att),
        _banrisk_text(token, campus, roll, sem, rows=att),
        _grades_text(token, campus, roll, sem, rows=marks),
    ]
    return ("\n\n" + fmt.RULE + "\n\n").join(parts)

def all_text(token, campus, roll, sem):
    """Gộp MỌI mục vào 1 tin: hôm nay → tuần → điểm → điểm thành phần → điểm danh → cấm thi → lịch thi.
    Lấy marks/att ĐÚNG 1 LẦN rồi chia sẻ cho các mục con -> không gọi trùng endpoint (nhẹ máy yếu)."""
    sessions = fetch_sessions(token, campus, roll, sem)
    marks = fetch_marks(token, campus, roll, sem)
    att = fetch_att(token, campus, roll, sem)
    today = _vn_now().date()
    parts = [
        _day_digest(sessions, today),
        _week_digest(sessions, today),
        _grades_text(token, campus, roll, sem, rows=marks),
        detail_text(token, campus, roll, sem, rows=marks),
        _att_text(token, campus, roll, sem, rows=att),
        _banrisk_text(token, campus, roll, sem, rows=att),
        exams_text(token, campus, roll, sem),
    ]
    return ("\n\n" + fmt.RULE + "\n\n").join(parts)

def handle(cmd, arg=None):
    """cmd: chuỗi lệnh (có/không dấu /!); arg: tham số (vd điểm cho whatif). Trả text.
    Bắt SystemExit (token hết hạn / chưa đăng nhập) -> trả LỜI thay vì làm sập bot/web."""
    cmd = (cmd or "").strip().lower().lstrip("/!").replace("_", "-")  # 'grades_detail' (menu) -> 'grades-detail'
    if cmd in ("", "start", "help"):
        return help_text()
    if cmd not in COMMANDS:
        return t(f"Lệnh không rõ: /{cmd}. Gõ /help.", f"Unknown command: /{cmd}. Try /help.")
    try:
        token, campus, roll = creds()                   # raise SystemExit nếu chưa đăng nhập
        sem = current_semester(token, campus, roll)
        subjects.load()                                  # tên + tín chỉ từ cache (nếu đã `fap subjects`)
        if cmd in ("today", "tomorrow", "week"):
            sessions = fetch_sessions(token, campus, roll, sem)
            today = _vn_now().date()
            if cmd == "week":
                return _week_digest(sessions, today)
            day = today + datetime.timedelta(days=1) if cmd == "tomorrow" else today
            return _day_digest(sessions, day)
        if cmd == "weekly":        return weekly_text(token, campus, roll, sem)
        if cmd == "grades":        return _grades_text(token, campus, roll, sem)
        if cmd == "grades-detail": return detail_text(token, campus, roll, sem)
        if cmd == "courses":       return courses_text(token, campus, roll, sem)
        if cmd == "attendance":    return _att_text(token, campus, roll, sem)
        if cmd == "banrisk":       return _banrisk_text(token, campus, roll, sem)
        if cmd == "whatif":        return _whatif_text(token, campus, roll, sem, arg)
        if cmd == "status":        return _status_text(token, campus, roll, sem)
        if cmd == "exams":         return exams_text(token, campus, roll, sem)
        if cmd == "exam-countdown":return countdown_text(token, campus, roll, sem)
        if cmd == "gpa":           return gpa_text(token, campus, roll)
        if cmd == "gpa-trend":     return trend_text(_fetch_transcript(token, campus, roll))
        if cmd == "credits":       return credits_overview(token, campus, roll)
        if cmd == "conduct":       return conduct_text(token, campus, roll, sem)
        if cmd == "notifications": return notifications_text(token, campus, roll)
        if cmd == "profile":       return profile_text(token, campus, roll)
        if cmd == "applications":  return applications_text(token, campus, roll)
        if cmd == "all":           return all_text(token, campus, roll, sem)
    except SystemExit as e:
        return str(e)
    return help_text()
