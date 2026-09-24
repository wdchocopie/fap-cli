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
from .api import (creds, call, call_login_retry, as_list, unwrap,
                  current_semester, check_auth, _vn_now)
from . import paths
from ..fmt import is_online, meet_url

OUT = paths.out_dir()          # output/ hoặc output/profiles/<tên>/ (xem core/paths.py)
TZID = "Asia/Ho_Chi_Minh"
_SLOT_RE = re.compile(r"\(?\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*\)?")

def _fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")

def _esc(t):
    return str(t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def _meet_raw(s):
    """Giá trị mã/link Meet thô của 1 buổi ('' nếu trống). Key gốc `meetURL`, bí danh `meeturl`."""
    return " ".join(str(s.get("meetURL") or s.get("meeturl") or "").split())

def fill_meet(sessions):
    """THUẦN: điền mã Meet còn thiếu cho từng buổi từ CHÍNH LỚP của nó (subjectCode + groupName).

    FAP chỉ gắn `meetURL` vào MỘT SỐ buổi của mỗi lớp (đo trên dump thật: vd 8/20 buổi CES202), trong
    khi mỗi lớp có đúng MỘT phòng Meet cố định (6/6 lớp: đúng 1 mã khác nhau). Không điền thì 9/11 buổi
    ONLINE trên dump thật KHÔNG có link. Chỉ mượn khi lớp có ĐÚNG MỘT mã (≥2 mã = mơ hồ, không đoán) và
    có subjectCode. Không sửa dict của caller: buổi được điền là bản SAO; thứ tự giữ nguyên."""
    codes = {}
    for s in sessions:
        if isinstance(s, dict) and s.get("subjectCode") and _meet_raw(s):
            codes.setdefault((s.get("subjectCode"), s.get("groupName") or ""), set()).add(_meet_raw(s))
    out = []
    for s in sessions:
        if isinstance(s, dict) and s.get("subjectCode") and not _meet_raw(s):
            got = codes.get((s.get("subjectCode"), s.get("groupName") or ""))
            if got and len(got) == 1:
                s = dict(s, meetURL=next(iter(got)))
        out.append(s)
    return out

def fetch_sessions(token, campus, roll, sem):
    http, data = call("GetActivityStudent",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return fill_meet(as_list(data))       # cả kỳ trong 1 lời gọi -> đủ ngữ cảnh để mượn mã Meet theo lớp

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
    # KHÔNG fill_meet ở đây: chỉ có 1 tuần nên KHÔNG kiểm được "lớp có đúng 1 mã" trên cả kỳ — một lớp có
    # 2 phòng Meet trong kỳ có thể trông như 1 mã trong tuần này ⇒ gắn NHẦM phòng. Buổi tự mang mã vẫn có link.
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

# ---------- Học kỳ + gom nhóm cả kỳ (THUẦN — không tốn thêm request) ----------
# GetActivityStudent chỉ nhận `Semester` (xem fetch_sessions) ⇒ MỘT lời gọi = LỊCH CẢ KỲ.
# Mọi hàm dưới đây (trừ fetch_semesters) là THUẦN: nhận list buổi/list kỳ, không mạng, không IO.

_DATE_FMTS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")

def parse_date(v):
    """THUẦN: '2026-09-15T00:00:00' | '09/15/2026' | '15/09/2026' -> date (None nếu không đọc được).
    Thứ tự format giống parse_session để 2 chỗ hiểu ngày y như nhau."""
    s = str(v if v is not None else "").strip().split("T")[0].split(" ")[0]
    if not s:
        return None
    for f in _DATE_FMTS:
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None

def _as_date(d):
    """datetime | date | None -> date | None (để trừ ngày không vỡ khi caller đưa datetime)."""
    if isinstance(d, datetime.datetime):
        return d.date()
    return d if isinstance(d, datetime.date) else None

def fetch_semesters(token, campus, roll):
    """GetSemester -> list[dict] (semesterName / termID / campusID / startDate / endDate), ~28 kỳ.
    Lỗi mạng/auth -> [] (caller phải im lặng bỏ qua phần phụ thuộc, đừng hiện 'None').

    ⚠️ Endpoint này ký bằng checksum_login (KHÔNG phải checksum mặc định) -> dùng api.call_login_retry
    y như api.current_semester, nếu gọi call() thường sẽ luôn nhận code 201."""
    try:
        _http, data = call_login_retry("GetSemester",
            [("campusCode", campus), ("Authen", token)], roll, campus)
        return [s for s in as_list(data) if isinstance(s, dict)]
    except Exception:
        return []

def semester_bounds(semesters, sem):
    """THUẦN: (ngày_bắt_đầu, ngày_kết_thúc) của kỳ tên `sem` trong danh sách GetSemester,
    (None, None) nếu không thấy / không đọc được ngày. So tên KHÔNG phân biệt hoa-thường."""
    key = str(sem or "").strip().lower()
    if not key:
        return None, None
    for s in semesters or []:
        if isinstance(s, dict) and str(s.get("semesterName") or "").strip().lower() == key:
            return parse_date(s.get("startDate")), parse_date(s.get("endDate"))
    return None, None

def canonical_semester(semesters, sem):
    """THUẦN: trả tên kỳ ĐÚNG CHÍNH TẢ như server (server phân biệt hoa-thường khi lọc lịch);
    không khớp -> trả nguyên chuỗi người dùng nhập."""
    key = str(sem or "").strip().lower()
    for s in semesters or []:
        if isinstance(s, dict) and str(s.get("semesterName") or "").strip().lower() == key:
            return s.get("semesterName") or sem
    return sem

def pick_semester(semesters, when=None):
    """THUẦN: tên kỳ ĐANG diễn ra vào ngày `when` (mặc định hôm nay giờ VN), None nếu không kỳ nào chứa.
    Cùng quy tắc với api.current_semester (kỳ khớp CUỐI CÙNG thắng) nhưng KHÔNG gọi lại mạng —
    nhờ vậy caller đã có sẵn danh sách kỳ thì không tốn thêm request."""
    day = _as_date(when) or _vn_now().date()
    hit = None
    for s in semesters or []:
        if not isinstance(s, dict):
            continue
        a, b = parse_date(s.get("startDate")), parse_date(s.get("endDate"))
        if a and b and a <= day <= b:
            hit = s.get("semesterName") or hit
    return hit or None

# Từ khoá chọn KIỂU XEM của `fap semester` — BẢNG DUY NHẤT, dùng chung cho cả CLI lẫn bot.
# (Trước đây bot_core giữ một bộ riêng chỉ có 3 từ tiếng Anh nên mọi bí danh tiếng Việt bị hiểu
#  nhầm thành TÊN KỲ → lệnh đi hỏi server một học kỳ không tồn tại.)
VIEW_WORDS = {"pattern": "pattern", "mẫu": "pattern", "mau": "pattern",
              "weeks": "weeks", "week": "weeks", "tuần": "weeks", "tuan": "weeks",
              "list": "list", "ds": "list", "ngày": "list", "ngay": "list", "all": "list"}

def norm_view(view):
    """THUẦN: từ khoá (kể cả bí danh tiếng Việt) -> 'pattern' | 'weeks' | 'list'. Lạ -> 'pattern'."""
    return VIEW_WORDS.get(str(view or "").strip().lower(), "pattern")

def upcoming_semesters(semesters, when=None, limit=8):
    """THUẦN: tên các kỳ CHƯA kết thúc tính từ `when`, sắp theo ngày bắt đầu, tối đa `limit`.
    Dùng để gợi ý khi người dùng hỏi một kỳ trường chưa xếp lịch."""
    day = _as_date(when) or _vn_now().date()
    rows = []
    for s in semesters or []:
        if not isinstance(s, dict):
            continue
        a, b = parse_date(s.get("startDate")), parse_date(s.get("endDate"))
        name = s.get("semesterName")
        if name and b and b >= day:
            rows.append((a or b, str(name)))
    rows.sort(key=lambda x: x[0])
    out = []
    for _, name in rows:
        if name not in out:
            out.append(name)
    return out[:limit] if limit else out

def week_index(start, end, day):
    """THUẦN: (tuần thứ mấy, tổng số tuần) của `day` trong kỳ [start, end] — cho header 'Tuần 5/15'.

    Tuần tính theo LỊCH (mốc thứ 2): tuần 1 = tuần chứa `start`, tuần cuối = tuần chứa `end`,
    nên một ngày cùng tuần với `start` nhưng trước `start` vẫn là tuần 1.
    Ngoài khoảng -> (None, tổng). Thiếu start/end/day (hoặc end < start) -> (None, None)."""
    start, end, day = _as_date(start), _as_date(end), _as_date(day)
    if not (start and end and day) or end < start:
        return None, None
    first = start - datetime.timedelta(days=start.weekday())          # thứ 2 của tuần đầu
    last = end + datetime.timedelta(days=6 - end.weekday())           # chủ nhật của tuần cuối
    total = ((last - first).days + 1) // 7
    if day < first or day > last:
        return None, total
    return (day - first).days // 7 + 1, total

def all_sessions_sorted(sessions):
    """THUẦN: [(start, end, buổi)] CẢ KỲ đã sort theo giờ bắt đầu (bản cả-kỳ của sessions_on_day).
    Buổi không đọc được ngày/giờ bị bỏ qua (giống build_ics)."""
    items = [(p[0], p[1], s) for s in sessions or [] if isinstance(s, dict)
             for p in [parse_session(s)] if p]
    items.sort(key=lambda x: x[0])
    return items

def group_by_week(sessions):
    """THUẦN: [buổi] -> [{"monday","sunday","items":[(start,end,buổi)],"subjects":{mã: số buổi}}],
    sắp theo thời gian. Tuần không có buổi nào thì KHÔNG xuất hiện (kỳ nghỉ giữa kỳ, tuần chưa xếp)."""
    weeks = {}
    for start, end, s in all_sessions_sorted(sessions):
        mon = start.date() - datetime.timedelta(days=start.weekday())
        w = weeks.setdefault(mon, {"monday": mon, "sunday": mon + datetime.timedelta(days=6),
                                   "items": [], "subjects": {}})
        w["items"].append((start, end, s))
        code = str(s.get("subjectCode") or "?")
        w["subjects"][code] = w["subjects"].get(code, 0) + 1
    return [weeks[k] for k in sorted(weeks)]

def weekly_pattern(sessions, min_repeat=3):
    """THUẦN: [buổi] -> {mã_môn: {"repeats": [...], "exceptions": [buổi lệch]}}.

    'repeats' = bộ (thứ, giờ bắt đầu, giờ kết thúc, phòng/online) lặp >= `min_repeat` lần trong kỳ,
    mỗi mục: {weekday(0=T2), start:'07:30', end:'09:00', room, online, count, first, last}.
    Buổi không thuộc bộ lặp nào (học bù, đổi phòng, thi) rơi vào 'exceptions' — TRẢ NGUYÊN buổi
    để renderer tự parse_session lấy ngày/giờ.

    ⚠️ Nguồn là GetActivityStudent (cả kỳ) — KHÔNG phản ánh buổi bị huỷ/nghỉ lễ;
    tuần nào nghi ngờ phải hỏi GetActivityStudentByWeek (xem fetch_week_activities)."""
    groups = {}
    for start, end, s in all_sessions_sorted(sessions):
        online = is_online(s)
        key = (str(s.get("subjectCode") or "?"), start.weekday(),
               start.strftime("%H:%M"), end.strftime("%H:%M"),
               "" if online else str(s.get("roomNo") or ""), online)
        groups.setdefault(key, []).append((start, s))
    out = {}
    for key, items in groups.items():
        subj, wd, hs, he, room, online = key
        d = out.setdefault(subj, {"repeats": [], "exceptions": []})
        if len(items) >= max(1, min_repeat):
            d["repeats"].append({"weekday": wd, "start": hs, "end": he, "room": room,
                                 "online": online, "count": len(items),
                                 "first": items[0][0].date(), "last": items[-1][0].date()})
        else:
            d["exceptions"] += [s for _, s in items]
    for d in out.values():
        d["repeats"].sort(key=lambda r: (r["weekday"], r["start"]))
        d["exceptions"].sort(key=lambda s: (parse_session(s) or (datetime.datetime.max,))[0])
    return out

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
        mu = meet_url(s)                  # mã Meet trần -> link đầy đủ; chỉ buổi online (xem fmt.meet_url)
        if mu:
            desc += f" • {mu}"
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
