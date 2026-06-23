#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schedule.py — Xuất thời khóa biểu FAP ra file .ics (import Google Calendar).

Nguồn: GetActivityStudent (mỗi buổi có ngày + giờ thật + phòng + môn).
Yêu cầu: đã đăng nhập (fap login) -> output/token.json.

Chạy (từ thư mục gốc repo):
    fap ics
=> output/lichhoc.ics  → Google Calendar: Settings → Import & Export → Import.
"""
import os, re, datetime
from .api import creds, call, as_list, unwrap, current_semester, check_auth
from ..fmt import is_online

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output")
TZID = "Asia/Ho_Chi_Minh"
_SLOT_RE = re.compile(r"\(?\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*\)?")

def _fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")

def _esc(t):
    return str(t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def fetch_sessions(token, campus, roll, sem):
    http, data = call("GetActivityStudent",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def fetch_week_by_date(token, campus, roll, day):
    """GetWeekByDate: ngày -> số tuần FAP. Trả dict {week, year, startDate, endDate} (hoặc {} nếu lỗi)."""
    http, data = call("GetWeekByDate",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll), ("date", day.strftime("%Y-%m-%d"))], roll, campus)
    check_auth(http, data)
    d = unwrap(data)
    return d if isinstance(d, dict) else {}

def fetch_week_activities(token, campus, roll, sem, week, year):
    """GetActivityStudentByWeek: TKB theo tuần (week+year) lấy thẳng từ server (chuẩn cho tuần nghỉ lễ)."""
    http, data = call("GetActivityStudentByWeek",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll),
         ("week", str(week)), ("year", str(year))], roll, campus)
    check_auth(http, data)
    return as_list(data)

def parse_session(s):
    """-> (start, end, ambiguous_bool) hoặc None nếu thiếu/không parse được ngày-giờ."""
    raw_date, slot_time = s.get("date"), s.get("slotTime", "")
    m = _SLOT_RE.search(slot_time or "")
    if not raw_date or not m:
        return None
    ds = str(raw_date).split(" ")[0]
    day = None
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try: day = datetime.datetime.strptime(ds, fmt).date(); break
        except ValueError: continue
    if not day:
        return None
    parts = re.split(r"[/-]", ds)
    ambiguous = len(parts) == 3 and all(p.isdigit() and int(p) <= 12 for p in parts[:2])
    h1, m1, h2, m2 = map(int, m.groups())
    start = datetime.datetime(day.year, day.month, day.day, h1, m1)
    end = datetime.datetime(day.year, day.month, day.day, h2, m2)
    if end <= start:                       # buổi kết thúc sang hôm sau
        end += datetime.timedelta(days=1)
    return start, end, ambiguous

def sessions_on_day(sessions, day):
    """Các buổi trong 'day' (date), ĐÃ sort theo giờ. Trả [(start, end, session), ...].
    Dùng chung cho notify/dashboard để khỏi lặp logic lọc+parse+sort."""
    items = [(p[0], p[1], s) for s in sessions
             for p in [parse_session(s)] if p and p[0].date() == day]
    items.sort(key=lambda x: x[0])
    return items

def build_ics(sessions):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FAP//Timetable//VI", "CALSCALE:GREGORIAN",
             "BEGIN:VTIMEZONE", f"TZID:{TZID}", "BEGIN:STANDARD", "DTSTART:19700101T000000",
             "TZOFFSETFROM:+0700", "TZOFFSETTO:+0700", "TZNAME:+07", "END:STANDARD", "END:VTIMEZONE"]
    count = skipped = ambiguous = 0
    for s in sessions:
        parsed = parse_session(s)
        if not parsed:
            skipped += 1; continue
        start, end, amb = parsed
        ambiguous += int(amb)
        subj, room = s.get("subjectCode", "Lớp"), s.get("roomNo", "")
        online = is_online(s)
        loc = "Online" if online else room
        desc = f"Môn {subj} • Lớp {s.get('groupName','')} • Slot {s.get('slot','')} • " \
               f"GV {s.get('lecturer','')} • Buổi {s.get('sessionNo','')}"
        if online and s.get("meetURL"):
            desc += f" • {s['meetURL']}"
        summary = subj + (f" @ {room}" if room and not online else (" (Online)" if online else ""))
        lines += [
            "BEGIN:VEVENT",
            f"UID:{subj}-{_fmt(start)}-{s.get('slot','')}@fap",
            f"SUMMARY:{_esc(summary)}",
            f"DTSTART;TZID={TZID}:{_fmt(start)}",
            f"DTEND;TZID={TZID}:{_fmt(end)}",
            f"LOCATION:{_esc(loc)}",
            f"DESCRIPTION:{_esc(desc)}",
            "END:VEVENT",
        ]
        count += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", count, skipped, ambiguous

def main():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print(f"campus={campus} roll={roll} kỳ={sem}")
    sessions = fetch_sessions(token, campus, roll, sem)
    print(f"Lấy được {len(sessions)} buổi.")
    ics, n, skipped, ambiguous = build_ics(sessions)
    if not n:
        print("Không có buổi hợp lệ để xuất lịch (token hết hạn / kỳ không đúng?)."); return
    if ambiguous:
        print(f"⚠️  {ambiguous} buổi có ngày DẠNG mơ hồ (ngày & tháng đều ≤12) — kiểm tra lại nếu lịch lệch ngày.")
    if skipped:
        print(f"⚠️  Bỏ qua {skipped} buổi không đọc được ngày/giờ.")
    os.makedirs(OUT, exist_ok=True)               # output/ có thể chưa tồn tại (checkout sạch / chưa login)
    path = os.path.join(OUT, "lichhoc.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"✓ Ghi {n} buổi -> output/lichhoc.ics")
    print("  Import: Google Calendar → Settings → Import & Export → chọn lichhoc.ics")

if __name__ == "__main__":
    main()
