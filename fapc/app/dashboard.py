#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard.py — Tổng quan 1 màn hình + lịch tuần + lịch CẢ KỲ.

    fap status            # (alias: fap dashboard) hôm nay + điểm + điểm danh + nguy cơ cấm thi
    fap week              # lịch tuần này (header có 'Tuần N/M' của kỳ)
    fap week next         # tuần sau   (prev/trước = tuần trước; hoặc số: fap week 2)
    fap semester          # CẢ KỲ: mẫu lịch lặp hằng tuần + buổi lệch mẫu
    fap semester weeks    # cả kỳ, mỗi tuần 1 dòng   |  fap semester list = liệt kê theo ngày
    fap semester Fall2026 # kỳ khác (kể cả kỳ sau) — thêm view: fap semester Fall2026 weeks

Gộp dữ liệu từ schedule + grades + attendance (mỗi lệnh ~3–4 lời gọi API).
`fap semester` KHÔNG tốn thêm request so với `fap week`: GetActivityStudent chỉ nhận `Semester`
nên 1 lời gọi đã trả TRỌN kỳ (trước đây `week()` lấy trọn rồi vứt 90%).
Định dạng (thứ, phòng/online, tiêu đề) dùng chung từ fmt.
"""
import os, json, datetime
from ..core.api import creds, current_semester, _vn_now, TOKEN_JSON
from ..core.schedule import (fetch_sessions, sessions_on_day, fetch_week_by_date, fetch_week_activities,
                             fetch_semesters, semester_bounds, canonical_semester, pick_semester,
                             upcoming_semesters, week_index, weekly_pattern, group_by_week,
                             all_sessions_sorted, parse_session)
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
    """Các dòng buổi học trong 'day' (date), đã sắp theo giờ bắt đầu. MỘT phần tử = MỘT buổi (status()
    in len() làm 'số buổi'); link Meet của buổi online nằm TRONG phần tử đó, sau '\\n'."""
    return [fmt.with_meet(f"   🕐 {a.strftime('%H:%M')}–{b.strftime('%H:%M')}  {s.get('subjectCode','')}  "
                          f"{fmt.room(s)}", s, indent="      ")
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

def _resolve_sem(token, campus, roll, sem=None):
    """-> (tên kỳ CHUẨN, danh sách kỳ GetSemester). DÙNG CHUNG 1 lời gọi GetSemester cho cả việc
    chọn kỳ hiện tại LẪN tra mốc ngày (thay vì gọi current_semester() rồi gọi GetSemester lần nữa)
    ⇒ `fap week` vẫn đúng 2 request như trước. Danh sách rỗng (lỗi mạng/auth) -> quay về
    current_semester() để giữ nguyên cảnh báo cũ; mốc ngày khi đó là (None, None) và header tự bỏ
    mảnh 'Tuần N/M' — KHÔNG bao giờ in 'Tuần None'."""
    sems = fetch_semesters(token, campus, roll)
    if sem:
        return canonical_semester(sems, sem), sems
    return (os.environ.get("FAP_SEMESTER") or pick_semester(sems)
            or current_semester(token, campus, roll)), sems

def _week_frag(sems, sem, day):
    """' · Tuần 5/15' khi tra được mốc kỳ, '' nếu không (im lặng — theo yêu cầu)."""
    n, total = week_index(*semester_bounds(sems, sem), day=day)
    if not n or not total:
        return ""
    return t(f" · Tuần {n}/{total}", f" · Week {n}/{total}")

def week(arg=None, sem=None):
    token, campus, roll = creds()
    sem, sems = _resolve_sem(token, campus, roll, sem)
    anchor = _vn_now().date() + datetime.timedelta(weeks=_week_offset(arg))
    monday, sunday = _week_bounds(anchor)
    span = f"{monday.strftime('%d/%m')}–{sunday.strftime('%d/%m/%Y')}"
    frag = _week_frag(sems, sem, anchor)
    print(fmt.header("📆", t(f"Lịch tuần {span} · {sem}{frag}",
                             f"Week {span} · {sem}{frag}")))
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

# ---------- Lịch CẢ KỲ (không tốn request thêm: GetActivityStudent trả TRỌN kỳ) ----------
_WD_SHORT_VI = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")   # dạng NGẮN chỉ dùng cho view cả kỳ (dòng dày đặc)
_EXC_CAP = 8                             # số buổi 'lệch mẫu' in tối đa (giữ 1 tin dưới cap Telegram/Discord)
# Bảng từ khoá view nằm ở core/schedule.py (NGUỒN DUY NHẤT — bot_core đọc cùng bảng đó).
# Giữ tên cũ ở đây cho các chỗ đang gọi.
from ..core.schedule import VIEW_WORDS as _VIEW_WORDS, norm_view as _norm_view

def _wd_short(i):
    """0..6 -> 'T2'..'CN' (vi) / 'Mon'..'Sun' (en). Bản dài fmt.weekday() vẫn dùng cho tiêu đề NGÀY."""
    i = int(i) % 7
    return t(_WD_SHORT_VI[i], fmt.WD_EN[i])

def _where(room, online):
    return "💻 Online" if online else (("📍" + str(room)) if str(room or "") else "")

def _repeat_bit(r):
    """'T2 07:30–09:00 📍BE-301 ×10'"""
    return " ".join(x for x in (f"{_wd_short(r['weekday'])} {r['start']}–{r['end']}",
                                _where(r["room"], r["online"]), f"×{r['count']}") if x)

def _exception_line(s):
    """'   • 12/09 T6 13:00 IAP301 📍BE-210'"""
    p = parse_session(s)
    code = s.get("subjectCode") or "?"
    if not p:
        return f"   • {code} " + t("(không đọc được ngày/giờ)", "(unreadable date/time)")
    a = p[0]
    bits = [a.strftime("%d/%m"), _wd_short(a.weekday()), a.strftime("%H:%M"), str(code),
            _where(s.get("roomNo"), fmt.is_online(s))]
    return "   • " + " ".join(b for b in bits if b)

def _honesty_note(skipped=0):
    """BẮT BUỘC: nguồn cả-kỳ KHÔNG phải nguồn chuẩn cho nghỉ lễ/huỷ buổi (xem core/schedule.py:42-43).
    `skipped` > 0: có buổi server trả về mà không đọc được ngày/giờ — phải NÓI RA, không nuốt im."""
    note = t("ℹ️ Mẫu suy từ lịch cả kỳ — KHÔNG phản ánh buổi huỷ / nghỉ lễ. Nghi ngờ tuần nào: fap week-exact",
             "ℹ️ Inferred from the term schedule — cancellations/holidays NOT reflected. Disputed week: fap week-exact")
    if skipped > 0:
        note = t(f"⚠️ {skipped} buổi không đọc được ngày/giờ → đã bỏ qua.",
                 f"⚠️ {skipped} session(s) had an unreadable date/time → skipped.") + "\n" + note
    return note

def _empty_semester_text(sem, sems=None, today=None):
    """Kỳ chưa xếp lịch (hay gặp khi xem kỳ SAU) -> báo rõ + gợi ý kỳ xem được, không để màn hình trống."""
    lines = [fmt.header("📚", t(f"Lịch cả kỳ {sem}", f"Full semester {sem}"), t("0 buổi", "0 sessions")),
             t("🚧 Kỳ này trường chưa xếp lịch (hoặc bạn chưa có môn nào) — FAP trả về 0 buổi.",
               "🚧 No timetable published for this term yet (or no enrolled subjects) — FAP returned 0 sessions.")]
    nxt = [n for n in upcoming_semesters(sems or [], when=today)
           if str(n).strip().lower() != str(sem or "").strip().lower()]   # đừng gợi ý lại chính kỳ vừa hỏi
    if nxt:
        lines.append(t("📅 Kỳ đang/sắp tới: " + ", ".join(nxt), "📅 Current/upcoming terms: " + ", ".join(nxt)))
        lines.append(t("   Xem kỳ khác:  fap semester <tên kỳ>", "   Other term:  fap semester <name>"))
    return "\n".join(lines)

def semester_view_text(sessions, sem, view=None, sems=None, today=None):
    """THUẦN: render lịch CẢ KỲ từ danh sách buổi (test offline được — không mạng, không IO).

    view: None/'pattern' (mặc định) = mẫu lặp hằng tuần + buổi lệch mẫu (gọn nhất, ~700 ký tự/kỳ)
          'weeks' = mỗi tuần 1 dòng (số thứ tự tuần, khoảng ngày, số buổi, môn nào mấy buổi)
          'list'  = liệt kê theo ngày (dài — caller nên fmt.chunks() khi gửi chat).
    `sems` (GetSemester) chỉ dùng để đánh SỐ TUẦN đúng theo kỳ và gợi ý kỳ khác khi rỗng."""
    view = _norm_view(view)
    items = all_sessions_sorted(sessions)
    # Buổi không đọc được ngày/giờ bị loại — ĐẾM và báo, đừng nuốt im (build_ics cũng trả `skipped`).
    # Im lặng ở đây nghĩa là người dùng thấy thiếu buổi mà không hiểu vì sao.
    skipped = len([s for s in (sessions or []) if isinstance(s, dict)]) - len(items)
    if not items:
        return _empty_semester_text(sem, sems, today)
    weeks = group_by_week(sessions)
    subjects = sorted({str(s.get("subjectCode") or "?") for _a, _b, s in items})
    first, last = items[0][0].date(), items[-1][0].date()
    span_d = f"{first.strftime('%d/%m/%Y')} – {last.strftime('%d/%m/%Y')}"
    lines = [fmt.header("📚", t(f"Lịch cả kỳ {sem}", f"Full semester {sem}"),
                        t(f"{len(items)} buổi", f"{len(items)} sessions")),
             t(f"🗓 {span_d} · {len(weeks)} tuần · {len(subjects)} môn",
               f"🗓 {span_d} · {len(weeks)} weeks · {len(subjects)} subjects")]

    if view == "list":
        cur = None
        for a, b, s in items:
            if a.date() != cur:
                cur = a.date()
                lines.append(f"\n📌 {fmt.weekday(cur)} · {cur.strftime('%d/%m/%Y')}")
            lines.append(fmt.with_meet(f"   🕐 {a.strftime('%H:%M')}–{b.strftime('%H:%M')}  "
                                       f"{s.get('subjectCode','')}  {fmt.room(s)}", s, indent="      "))
        return "\n".join(lines + ["\n" + _honesty_note(skipped)])

    if view == "weeks":
        start, end = semester_bounds(sems or [], sem)
        lines.append("")
        for i, w in enumerate(weeks, 1):
            n = week_index(start, end, w["monday"])[0] or i          # số tuần THẬT của kỳ nếu tra được
            roll = " ".join(f"{c}×{k}" for c, k in sorted(w["subjects"].items()))
            rng = f"{w['monday'].strftime('%d/%m')}–{w['sunday'].strftime('%d/%m')}"
            lines.append(t(f"📌 Tuần {n} · {rng} · {len(w['items'])} buổi: {roll}",
                           f"📌 Week {n} · {rng} · {len(w['items'])} sessions: {roll}"))
        return "\n".join(lines + ["", _honesty_note(skipped)])

    pat = weekly_pattern(sessions)
    body = [f"🔁 {c}: " + " · ".join(_repeat_bit(r) for r in pat[c]["repeats"])
            for c in subjects if pat.get(c) and pat[c]["repeats"]]
    lines += [""] + (body or [t("(không có mẫu lặp — thử: fap semester list)",
                                "(no weekly pattern — try: fap semester list)")])
    excs = [s for c in subjects for s in (pat.get(c) or {}).get("exceptions", [])]
    excs.sort(key=lambda s: (parse_session(s) or (datetime.datetime.max,))[0])
    if excs:
        lines += ["", t(f"⚠️ Lệch mẫu ({len(excs)} buổi):", f"⚠️ Off-pattern ({len(excs)} sessions):")]
        lines += [_exception_line(s) for s in excs[:_EXC_CAP]]
        if len(excs) > _EXC_CAP:
            lines.append(t(f"   …+{len(excs) - _EXC_CAP} buổi nữa", f"   …+{len(excs) - _EXC_CAP} more"))
    return "\n".join(lines + ["", _honesty_note(skipped)])

def semester_text(token, campus, roll, sem, view=None):
    """Lịch CẢ KỲ -> chuỗi (cho bot/CLI). 1 request cho view mặc định; chỉ gọi thêm GetSemester khi
    cần đánh số tuần ('weeks') hoặc khi kỳ RỖNG (để gợi ý kỳ khác)."""
    sessions = fetch_sessions(token, campus, roll, sem)
    sems = []
    if not sessions:
        # Rỗng có thể chỉ vì GÕ SAI HOA/THƯỜNG: server phân biệt hoa-thường ở tham số Semester
        # ('fall2026' ≠ 'Fall2026'). Chuẩn hoá rồi THỬ LẠI — nếu không, người dùng bị báo "chưa xếp
        # lịch" cho đúng cái kỳ đang có thật. Chỉ tốn thêm request ở ĐƯỜNG RỖNG; kỳ gõ đúng vẫn 1 request.
        sems = fetch_semesters(token, campus, roll)
        canon = canonical_semester(sems, sem)
        if canon and canon != sem:
            sem = canon
            sessions = fetch_sessions(token, campus, roll, sem)
    if not sems and _norm_view(view) == "weeks":      # view 'weeks' cần mốc ngày để đánh số tuần
        sems = fetch_semesters(token, campus, roll)
    return semester_view_text(sessions, sem, view=view, sems=sems)

def _split_semester_args(a, b=None):
    """('weeks', None) | ('Fall2026', 'list') | (None, None) -> (tên kỳ | None, view | None).
    Người dùng gõ thứ tự nào cũng được: `fap semester weeks Fall2026` = `fap semester Fall2026 weeks`."""
    sem = view = None
    for x in (a, b):
        s = str(x).strip() if x is not None else ""
        if not s:
            continue
        if s.lower() in _VIEW_WORDS:
            view = s.lower()
        else:
            sem = s
    return sem, view

def semester(arg=None, arg2=None):
    """In lịch cả kỳ (mặc định kỳ hiện tại). arg/arg2 = view ('weeks'/'list') và/hoặc TÊN KỲ khác."""
    sem_arg, view = _split_semester_args(arg, arg2)
    token, campus, roll = creds()
    sem, sems = _resolve_sem(token, campus, roll, sem_arg)
    sessions = fetch_sessions(token, campus, roll, sem)
    print(semester_view_text(sessions, sem, view=view, sems=sems))

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
    """1 buổi của TKB-theo-tuần. GetActivityStudentByWeek trả CÙNG cờ isOnline + meetURL như
    GetActivityStudent (bundle app đọc cả hai ở nhánh theo-tuần) -> hiện 'Online' + link Meet. Thiếu
    field thì is_online=False -> ra đúng như cũ ('📍 <phòng>'), không hỏng gì."""
    subj = r.get("subjectCode", "")
    room = _first(r.get("roomNo"), r.get("room"))
    slot = _first(r.get("slotTime"), r.get("slot"))
    where = "💻 Online" if fmt.is_online(r) else (("📍 " + str(room)) if str(room) != "" else "")
    bits = [f"slot {slot}" if str(slot) != "" else "", subj, where, str(r.get("lecturer") or "")]
    return fmt.with_meet("   🕐 " + "  ".join(b for b in bits if b), r, indent="      ")

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
    argv = sys.argv[1:]
    if argv and argv[0] == "week":
        week(argv[1] if len(argv) > 1 else None)
    elif argv and argv[0] in ("semester", "kỳ", "ky"):
        semester(*(argv[1:3] or [None]))
    else:
        status()

if __name__ == "__main__":
    main()
