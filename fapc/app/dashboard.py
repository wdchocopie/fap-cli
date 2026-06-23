#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard.py — Tổng quan 1 màn hình + lịch tuần.

    fap status            # (alias: fap dashboard) hôm nay + điểm + điểm danh + nguy cơ cấm thi
    fap week              # lịch tuần này
    fap week next         # tuần sau   (prev/trước = tuần trước; hoặc số: fap week 2)

Gộp dữ liệu từ schedule + grades + attendance (mỗi lệnh ~3–4 lời gọi API).
Định dạng (thứ, phòng/online, tiêu đề) dùng chung từ fmt.
"""
import json, datetime
from ..core.api import creds, current_semester, _vn_now, TOKEN_JSON
from ..core.schedule import fetch_sessions, sessions_on_day, fetch_week_by_date, fetch_week_activities
from ..core.grades import fetch_marks, _gpa
from ..core.attendance import fetch as fetch_att, _at_risk, BAN_THRESHOLD
from ..i18n import t
from .. import fmt

def _ident():
    try:
        m = json.load(open(TOKEN_JSON, encoding="utf-8"))
        return m.get("fullname") or "", m.get("email") or ""
    except Exception:
        return "", ""

def _day_lines(sessions, day):
    """Các dòng buổi học trong 'day' (date), đã sắp theo giờ bắt đầu."""
    return [f"   🕐 {a.strftime('%H:%M')}–{b.strftime('%H:%M')}  {s.get('subjectCode','')}  {fmt.room(s)}"
            for a, b, s in sessions_on_day(sessions, day)]

def _week_bounds(day):
    monday = day - datetime.timedelta(days=day.weekday())
    return monday, monday + datetime.timedelta(days=6)

def status():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    name, _ = _ident()
    now = _vn_now(); today = now.date()
    print(fmt.header("📋", t("FAP · Tổng quan", "FAP · Status")))
    print(f"👤 {name}  ({roll} · {campus})")
    print(t(f"📆 Kỳ {sem} · {fmt.weekday(today)} {today.strftime('%d/%m/%Y')} {now.strftime('%H:%M')} (giờ VN)",
            f"📆 {sem} · {fmt.weekday(today)} {today.strftime('%d/%m/%Y')} {now.strftime('%H:%M')} (VN time)"))

    sessions = fetch_sessions(token, campus, roll, sem)
    lines = _day_lines(sessions, today)
    print(t(f"\n📅 Hôm nay · {len(lines)} buổi:", f"\n📅 Today · {len(lines)} sessions:"))
    print("\n".join(lines) if lines else t("   🎉 (không có buổi học)", "   🎉 (no classes)"))

    rows = fetch_marks(token, campus, roll, sem)
    g = fmt.gpa_val(_gpa(rows)); graded = sum(1 for r in rows if fmt.has_mark(r))
    print(t(f"\n📊 Điểm: {graded}/{len(rows)} môn có điểm · GPA tạm tính {g}",
            f"\n📊 Grades: {graded}/{len(rows)} graded · provisional GPA {g}"))

    arows = fetch_att(token, campus, roll, sem)
    print(t(f"\n🟢 Điểm danh ({len(arows)} môn):", f"\n🟢 Attendance ({len(arows)} subjects):"))
    risk = []
    for r in arows:
        atrisk = _at_risk(r)
        if atrisk: risk.append(r.get("subjectCode", ""))
        print(f"   • {r.get('subjectCode','')} — {r.get('attendance','')}%" + ("  ⚠️" if atrisk else ""))
    if risk:
        print(t(f"   ⚠️ Nguy cơ cấm thi (<{BAN_THRESHOLD}%): " + ", ".join(risk),
                f"   ⚠️ Exam-ban risk (<{BAN_THRESHOLD}%): " + ", ".join(risk)))

def _week_offset(arg):
    if arg is None: return 0
    s = str(arg).strip().lower()
    if s in ("next", "sau", "+1"): return 1
    if s in ("prev", "previous", "truoc", "trước", "-1"): return -1
    try: return int(s)
    except ValueError: return 0

def week(arg=None):
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    anchor = _vn_now().date() + datetime.timedelta(weeks=_week_offset(arg))
    monday, sunday = _week_bounds(anchor)
    print(fmt.header("📆", t(f"Lịch tuần {monday.strftime('%d/%m')}–{sunday.strftime('%d/%m/%Y')} · {sem}",
                             f"Week {monday.strftime('%d/%m')}–{sunday.strftime('%d/%m/%Y')} · {sem}")))
    sessions = fetch_sessions(token, campus, roll, sem)
    total = 0
    for i in range(7):
        d = monday + datetime.timedelta(days=i)
        lines = _day_lines(sessions, d)
        head = f"📌 {fmt.weekday(d)} · {d.strftime('%d/%m')}"
        if lines:
            total += len(lines)
            print(f"\n{head}"); print("\n".join(lines))
        else:
            print(f"\n{head} — " + t("nghỉ", "off"))
    print(t(f"\nTổng: {total} buổi trong tuần.", f"\nTotal: {total} sessions this week."))

# ---------- TKB theo tuần lấy THẲNG từ server (GetActivityStudentByWeek) ----------
def _byweek_date(r):
    raw = str(r.get("date") or "").split("T")[0].split(" ")[0]
    for f in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(raw, f).date()
        except ValueError: continue
    return None

def _first(*vals):
    """Giá trị đầu tiên KHÁC None và rỗng — tránh `or` nuốt mất số 0 (slot/room = 0)."""
    for v in vals:
        if v is not None and v != "":
            return v
    return ""

def _byweek_line(r):
    subj = r.get("subjectCode", "")
    room = _first(r.get("roomNo"), r.get("room"))
    slot = _first(r.get("slotTime"), r.get("slot"))
    bits = [f"slot {slot}" if str(slot) != "" else "", subj,
            ("📍 " + str(room)) if str(room) != "" else "", str(r.get("lecturer") or "")]
    return "   🕐 " + "  ".join(b for b in bits if b)

def week_exact_text(rows, week, year):
    """Render TKB-theo-tuần (THUẦN, test được). Group theo ngày, field generic vì shape chưa kiểm chứng."""
    if not rows:
        return t(f"📆 Tuần {week}/{year}: không có buổi (nghỉ lễ?) hoặc server trả rỗng.",
                 f"📆 Week {week}/{year}: no sessions (holiday?) or server returned empty.")
    groups = {}
    for r in rows:
        d = _byweek_date(r) if isinstance(r, dict) else None
        groups.setdefault(d.toordinal() if d else 10**9, (d, []))[1].append(r)
    lines = [fmt.header("📆", t(f"TKB tuần {week}/{year}", f"Timetable week {week}/{year}"), str(len(rows)))]
    for ordv in sorted(groups):
        d, rs = groups[ordv]
        label = f"{fmt.weekday(d)} · {d.strftime('%d/%m/%Y')}" if d else (
            rs[0].get("dayOfWeek") if isinstance(rs[0], dict) and rs[0].get("dayOfWeek") else t("(ngày khác)", "(other)"))
        lines.append(f"\n📌 {label}")
        lines += [_byweek_line(r) for r in rs if isinstance(r, dict)]
    return "\n".join(lines)

def week_exact(week=None, year=None):
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    if week is None:                                  # tự dò số tuần FAP từ ngày hôm nay
        wb = fetch_week_by_date(token, campus, roll, _vn_now().date())
        week = wb.get("week") or wb.get("Week")
        year = year or wb.get("year") or wb.get("Year")
        if not week:
            print(t("Không tự xác định được tuần (GetWeekByDate rỗng/lỗi). Dùng: fap week-exact <week> <year>  — hoặc  fap week.",
                    "Couldn't resolve the week (GetWeekByDate empty). Use: fap week-exact <week> <year>  — or  fap week.")); return
    year = year or _vn_now().year
    print(week_exact_text(fetch_week_activities(token, campus, roll, sem, week, year), week, year))

def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "week":
        week(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        status()

if __name__ == "__main__":
    main()
