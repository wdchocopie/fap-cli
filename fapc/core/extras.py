#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extras.py — tra cứu nhỏ: lịch thi, tin tức, học phí/số dư.

    fap exams   # GetScheduleExam   (cũng dùng cho `fap notify exams` + bot /exams)
    fap news    # GetTop10News
    fap fees    # GetBalance + GeFeeByRoll

Endpoint có thể RỖNG/404 với tài khoản chưa tới kỳ thi / chưa có dữ liệu — xử lý rỗng đàng hoàng.
"""
import os, re, datetime
from .api import creds, call, unwrap, as_list, current_semester, checksum_auth, check_auth, _vn_now
from . import subjects, paths
from ..i18n import t
from .. import fmt

# ---------- HỒ SƠ SINH VIÊN (GetStudentById) ----------
_PROFILE_ROWS = [            # (key, nhãn_vi, nhãn_en) — chỉ hiện field có giá trị
    ("rollNumber", "MSSV", "Roll"), ("email", "Email", "Email"),
    ("dateOfBirth", "Ngày sinh", "DOB"), ("gender", "Giới tính", "Gender"),
    ("major", "Ngành", "Major"), ("nganh", "Ngành", "Major"), ("chuyenNganh", "Chuyên ngành", "Specialization"),
    ("batch", "Khoá", "Batch"), ("lopchinh", "Lớp", "Class"), ("currentTermNo", "Kỳ hiện tại", "Term"),
    ("mobilePhone", "SĐT", "Phone"), ("iDCard", "CCCD", "ID card"), ("statusCode", "Trạng thái", "Status"),
]

def fetch_profile(token, campus, roll):
    http, data = call("GetStudentById", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def profile_text(token, campus, roll):
    rows = fetch_profile(token, campus, roll)
    if not rows or not isinstance(rows[0], dict):
        return t("👤 Không lấy được hồ sơ.", "👤 Couldn't fetch profile.")
    r = rows[0]
    out = [fmt.header("👤", fmt.unescape(r.get("fullname")) or t("Hồ sơ", "Profile"), fmt.unescape(r.get("rollNumber")))]
    seen = set()
    for key, vi, en in _PROFILE_ROWS:
        if key == "dateOfBirth":
            v = fmt.fmt_date(r["dateOfBirth"]) if r.get("dateOfBirth") else ""
        elif key == "gender":
            g = r.get("gender")
            v = "" if g in (None, "") else (t("Nam", "Male") if g in (True, "true", "True", 1, "1") else t("Nữ", "Female"))
        else:
            v = fmt.unescape(r.get(key))
        label = t(vi, en)
        if v and label not in seen:          # 'major'/'nganh' cùng nhãn 'Ngành' -> chỉ hiện 1
            seen.add(label); out.append(f"• {label}: {v}")
    return "\n".join(out)

def profile():
    token, campus, roll = creds()
    print(profile_text(token, campus, roll))

# ---------- ĐƠN TỪ (GetApplication) ----------
def _appl_date(r):
    raw = str(r.get("createDate") or "").split("T")[0].split(" ")[0]
    for f in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(raw, f).date()
        except ValueError: continue
    return None

def fetch_applications(token, campus, roll):
    http, data = call("GetApplication", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def applications_text(token, campus, roll):
    rows = [r for r in fetch_applications(token, campus, roll) if isinstance(r, dict)]
    if not rows:
        return t("📄 Chưa có đơn từ nào.", "📄 No applications.")
    rows.sort(key=lambda r: _appl_date(r) or datetime.date.min, reverse=True)   # mới nhất trước
    out = [fmt.header("📄", t("Đơn từ", "Applications"), str(len(rows)))]
    for r in rows:
        name = fmt.unescape(r.get("name")) or t("(đơn)", "(application)")
        date = fmt.unescape(r.get("createDate"))
        out.append(f"\n• {name}" + (f"  ·  {date}" if date else ""))
        note = fmt.unescape(r.get("processNote"))           # phản hồi của phòng ban (decode &#xxx;)
        if note:
            out.append(f"   ↳ {note}")
    return "\n".join(out)

def applications():
    token, campus, roll = creds()
    print(applications_text(token, campus, roll))

# ---------- DANH SÁCH CAMPUS (giúp người MỚI biết campusCode TRƯỚC khi login) ----------
def campuses_text():
    """GetAllActiveCampus — KHÔNG cần token/đăng nhập. Trả bảng campusCode + tên (chọn campus trước `fap login`)."""
    http, data = call("GetAllActiveCampus", [], "", "", checksum_value=False)   # endpoint công khai, không checksum
    rows = as_list(data)
    if not rows:
        return t("Không lấy được danh sách campus (kiểm tra mạng).", "Couldn't fetch campus list (check network).")
    return t(f"== Campus đang hoạt động ({len(rows)}) ==", f"== Active campuses ({len(rows)}) ==") + "\n" + fmt.table(rows)

def campuses():
    print(campuses_text())

# ---------- LỊCH THI (có bản trả-text cho bot/notify) ----------
# GetScheduleExam trả mỗi môn 1 dict. Dữ liệu THẬT (đã xác nhận): subjectCode + examDate ('m/d/Y') +
# examTime ('HH:MM') + examRoom; có thể kèm examType (PE/FE/2ndFE…) / examForm / groupName. Tên field
# đổi theo campus/kỳ -> DÒ ĐA BIẾN-THỂ (không phân biệt hoa/thường) như courses.py, đừng cứng 1 tên.
_EX_SUBJ  = ("subjectcode", "subject", "examsubject")
_EX_ROOM  = ("examroom", "room", "roomno", "phongthi", "examroomname")
_EX_TYPE  = ("examtype", "type", "publicexamtype")
_EX_FORM  = ("examform", "form", "method", "examformat")

def _exam_get(r, keys):
    """Giá trị đầu tiên KHÁC RỖNG trong các key ứng viên (không phân biệt hoa/thường). '' nếu không có."""
    if not isinstance(r, dict):
        return ""
    low = {str(k).lower(): v for k, v in r.items()}
    for k in keys:
        v = low.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""

def _exam_line(r):
    """1 dòng lịch thi ĐÃ ĐỊNH DẠNG (thay cho việc đổ thô mọi value):
    '• MÃ — Tên môn — DD/MM/YYYY HH:MM  📍 phòng  · type · form'. Trả (dòng, start_dt|None) để sort."""
    subj = _exam_get(r, _EX_SUBJ) or "?"
    dt = _exam_dt(r) if isinstance(r, dict) else None       # parse ngày/giờ generic (m/d/Y ưu tiên)
    if dt:
        when = dt[0].strftime("%d/%m/%Y %H:%M")
    else:                                                    # không parse được -> hiện thô cái đang có
        when = " ".join(x for x in (_exam_get(r, ("examdate", "date")),
                                    _exam_get(r, ("examtime", "time"))) if x)
    room = _exam_get(r, _EX_ROOM)
    tags = [b for b in (_exam_get(r, _EX_TYPE), _exam_get(r, _EX_FORM)) if b]
    line = f"• {subjects.label(subj)}"
    if when:
        line += f" — {when}"
    if room:
        line += f"  📍 {room}"
    if tags:
        line += "  · " + " · ".join(tags)
    return line, (dt[0] if dt else None)

def exams_text(token, campus, roll, sem):
    http, data = call("GetScheduleExam",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem), ("Authen", token)], roll, campus)
    check_auth(http, data)        # token hết hạn -> raise rõ, KHÔNG báo nhầm "chưa có lịch thi"
    rows = [r for r in as_list(data) if isinstance(r, dict)]
    if not rows:
        return t(f"📝 Chưa có lịch thi kỳ {sem} (sẽ hiện khi trường xếp lịch).",
                 f"📝 No exam schedule for {sem} yet (appears once scheduled).")
    subjects.load()                                          # tên môn từ cache (nếu đã `fap subjects`)
    rendered = [_exam_line(r) for r in rows]
    rendered.sort(key=lambda x: x[1] or datetime.datetime.max)   # sớm nhất trước; không-parse-được xuống cuối
    lines = [fmt.header("📝", t(f"Lịch thi {sem}", f"Exam schedule {sem}"),
                        t(f"{len(rows)} môn", f"{len(rows)} exams"))]
    lines += [ln for ln, _ in rendered]
    return "\n".join(lines)

def exams():
    token, campus, roll = creds()
    print(exams_text(token, campus, roll, current_semester(token, campus, roll)))

# ---------- TIN TỨC ----------
def fetch_news(token, campus, roll, keyword=None, type="1"):
    """GetTop10News (mặc định) HOẶC SearchNews khi có `keyword`. checksum_auth(type, campus) (như GetTop10News).
    Trả list dict đã decode entity. Rỗng nếu lỗi/không có.
    type mặc định '1' — bảng tin chung của trường (đã probe live: type '0' thường RỖNG với nhiều campus)."""
    if keyword:
        http, data = call("SearchNews",
            [("campusCode", campus), ("Authen", token), ("keysearch", keyword), ("type", str(type))],
            roll, campus, checksum_value=checksum_auth(str(type), campus))
    else:
        http, data = call("GetTop10News", [("campusCode", campus), ("Authen", token), ("type", str(type))],
                          roll, campus, checksum_value=checksum_auth(str(type), campus))
    check_auth(http, data)
    return [{k: fmt.unescape(v) if isinstance(v, str) else v for k, v in r.items()}
            for r in as_list(data) if isinstance(r, dict)]

def _news_get(n, keys):
    """Giá trị đầu tiên KHÁC RỖNG trong các khóa ứng viên (field tin của FAP đổi theo campus/kỳ)."""
    for k in keys:
        if isinstance(n, dict) and n.get(k) not in (None, ""):
            return n[k]
    return ""

def _html_snippet(raw, limit=180):
    """THUẦN: bóc thẻ HTML + decode entity + gộp khoảng trắng -> đoạn trích 1 dòng (≤limit). Rỗng -> ''."""
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw))               # bỏ thẻ
    txt = re.sub(r"\s+", " ", fmt.unescape(txt)).strip()  # &nbsp;/&amp;… + gộp trắng (kể cả \xa0)
    return (txt[:limit].rstrip() + "…") if len(txt) > limit else txt

def _news_line(n):
    """1 mục tin GỌN: tiêu đề + ngày + trích ngắn. Field FAP thật: 'tittle' (typo của FAP), 'content', 'createDate'."""
    title = fmt.unescape(_news_get(n, ("tittle", "title", "subject"))) or t("(không tiêu đề)", "(no title)")
    date = fmt.fmt_date(_news_get(n, ("createDate", "editDate", "entryDate", "date")))
    snippet = _html_snippet(_news_get(n, ("content", "body", "description")))
    line = f"• {title}"
    if date:
        line += f"\n   🗓 {date}"
    if snippet:
        line += f"\n   {snippet}"
    return line

def news_text(token, campus, roll, keyword=None, type="1", limit=10):
    """Tin tức render SẠCH (tiêu đề + ngày + trích, MỚI NHẤT trước) — thay bảng thô đổ nguyên HTML."""
    rows = fetch_news(token, campus, roll, keyword, type)
    if not rows:
        return t(f"📰 Không có tin{' khớp ' + repr(keyword) if keyword else ''}.",
                 f"📰 No news{' matching ' + repr(keyword) if keyword else ''}.")
    rows = sorted(rows, key=lambda n: str(_news_get(n, ("createDate", "editDate", "entryDate")) or ""),
                  reverse=True)[:limit]
    head = t(f"Tin tức · tìm {keyword!r}", f"News · search {keyword!r}") if keyword else t("Tin tức", "News")
    return "\n".join([fmt.header("📰", head, str(len(rows)))] + [_news_line(n) for n in rows])

def news(keyword=None, type="1"):
    token, campus, roll = creds()
    print(news_text(token, campus, roll, keyword, type))

# ---------- HỌC PHÍ / SỐ DƯ ----------
def fees():
    token, campus, roll = creds()
    http, bal = call("GetBalance", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, bal)         # nếu không, in nguyên envelope lỗi 201 thành "số dư"
    print(t(f"💰 Số dư tài khoản: {unwrap(bal)}", f"💰 Account balance: {unwrap(bal)}"))
    http, fee = call("GeFeeByRoll", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, fee)
    rows = as_list(fee)
    if rows:
        print(t("Chi tiết học phí:", "Fee details:")); print(fmt.table(rows))
    else:
        print(t("(Chưa có chi tiết học phí cho tài khoản này.)", "(No fee details for this account.)"))

# ---------- THÔNG BÁO CÁ NHÂN (GetNotificationByRoll) ----------
def fetch_notifications(token, campus, roll):
    http, data = call("GetNotificationByRoll",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _notif_line(n):
    """1 dòng gọn cho 1 thông báo (field thật: title/entryDate/entryBy). Decode HTML entity."""
    title = fmt.unescape(n.get("title")) or t("(không tiêu đề)", "(no title)")
    meta = " · ".join(x for x in (fmt.fmt_date(n.get("entryDate")) if n.get("entryDate") else "",
                                  fmt.unescape(n.get("entryBy"))) if x)
    return f"• {title}" + (f"\n   {meta}" if meta else "")

def notifications_text(token, campus, roll, limit=10):
    rows = fetch_notifications(token, campus, roll)
    if not rows:
        return t("🔔 Không có thông báo.", "🔔 No notifications.")
    rows = sorted(rows, key=lambda n: str(n.get("entryDate") or ""), reverse=True)[:limit]
    lines = [fmt.header("🔔", t("Thông báo mới nhất", "Latest notifications"), str(len(rows)))]
    return "\n".join(lines + [_notif_line(n) for n in rows])

def notifications():
    token, campus, roll = creds()
    print(notifications_text(token, campus, roll))

# ---------- XUẤT LỊCH THI -> .ics (Calendar TỰ NHẮC trước 1 ngày) ----------
def _exam_rows(token, campus, roll, sem):
    http, data = call("GetScheduleExam",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem), ("Authen", token)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _exam_dt(r):
    """(start, end) từ 1 dòng lịch thi — parse generic ngày + giờ. None nếu không đọc được ngày."""
    import re, datetime
    dv = next((r[k] for k in r if str(k).lower() in ("examdate", "date", "ngaythi", "examday") and r[k]), None)
    if not dv:
        return None
    ds = str(dv).split("T")[0].split(" ")[0]
    day = None
    for f in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try: day = datetime.datetime.strptime(ds, f).date(); break
        except ValueError: continue
    if not day:
        return None
    def _clock(s):
        # chấp nhận '07h30' (FAP dùng 'h') và '07:30'; lấy giờ ĐẦU nếu là khoảng '07h30-08h50'
        m = re.search(r"(\d{1,2})\s*[h:]\s*(\d{2})", str(s or ""))
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            return int(m.group(1)), int(m.group(2))
        return None
    hh, mm = 7, 0
    tv = next((r[k] for k in r if str(k).lower() in ("examtime", "time", "giothi", "starttime") and r[k]), None)
    for src in (tv, dv):                 # ưu tiên field GIỜ riêng (vd '07h30-08h50'), rồi giờ nhúng trong field ngày
        c = _clock(src)
        if c and c != (0, 0):            # bỏ '00:00' GIẢ từ field ngày dạng '...T00:00:00'
            hh, mm = c; break
    s = datetime.datetime(day.year, day.month, day.day, hh, mm)
    return s, s + datetime.timedelta(hours=2)

# ---------- ĐẾM NGƯỢC LỊCH THI (exam-countdown) ----------
def exam_countdown(rows, now):
    """THUẦN: [(days, start_dt, subjectCode, room)] cho kỳ thi SẮP tới (bỏ đã qua), sớm nhất trước.
    `now` truyền vào (datetime naive, giờ VN) → test offline được. Dùng lại `_exam_dt` (parse generic)."""
    out = []
    for r in rows or []:
        dt = _exam_dt(r)
        if not dt:
            continue
        days = (dt[0].date() - now.date()).days
        if days < 0:                                   # đã thi xong → bỏ
            continue
        subj = r.get("subjectCode") or r.get("subjectName") or "?"
        out.append((days, dt[0], str(subj), str(r.get("examRoom") or r.get("roomNo") or r.get("room") or "")))
    out.sort(key=lambda x: x[1])
    return out

def countdown_text(token, campus, roll, sem, now=None):
    now = now or _vn_now().replace(tzinfo=None)
    subjects.load()
    items = exam_countdown(_exam_rows(token, campus, roll, sem), now)
    if not items:
        return t("⏳ Chưa có lịch thi sắp tới.", "⏳ No upcoming exams.")
    out = [fmt.header("⏳", t(f"Đếm ngược thi · {sem}", f"Exam countdown · {sem}"),
                      t(f"{len(items)} môn", f"{len(items)} exams"))]
    for days, start, subj, room in items:
        if days == 0:   tag = t("🔴 HÔM NAY", "🔴 TODAY")
        elif days == 1: tag = t("🟠 NGÀY MAI", "🟠 TOMORROW")
        elif days <= 3: tag = t(f"🟡 còn {days} ngày", f"🟡 in {days} days")
        else:           tag = t(f"⚪ còn {days} ngày", f"⚪ in {days} days")
        line = f"• {subjects.label(subj)} — {start.strftime('%d/%m %H:%M')}  {tag}"
        if room:
            line += f"  📍 {room}"
        out.append(line)
    return "\n".join(out)

def exam_countdown_cmd():
    token, campus, roll = creds()
    print(countdown_text(token, campus, roll, current_semester(token, campus, roll)))

def build_exam_ics(rows):
    """THUẦN: rows GetScheduleExam -> (ics_str, n_events, n_skipped). Mỗi môn kèm VALARM -P1D (nhắc trước 1 ngày)."""
    from .schedule import _esc, _fmt, TZID
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FAP//Exams//VI", "CALSCALE:GREGORIAN"]
    n = skipped = 0
    for r in rows:
        p = _exam_dt(r) if isinstance(r, dict) else None
        if not p:
            skipped += 1; continue
        s, e = p
        subj = _exam_get(r, _EX_SUBJ) or "Thi"
        room = _exam_get(r, _EX_ROOM)
        desc = " • ".join(b for b in (f"Môn {subj}", f"Phòng {room}" if room else "",
                                      _exam_get(r, _EX_TYPE), _exam_get(r, _EX_FORM)) if b)
        lines += ["BEGIN:VEVENT", f"UID:exam-{subj}-{_fmt(s)}-{n}@fap", f"SUMMARY:{_esc('[Thi] ' + str(subj))}",
                  f"DTSTART;TZID={TZID}:{_fmt(s)}", f"DTEND;TZID={TZID}:{_fmt(e)}",
                  f"LOCATION:{_esc(room)}", f"DESCRIPTION:{_esc(desc)}",
                  "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:Nhac thi (truoc 1 ngay)", "END:VALARM",
                  "END:VEVENT"]
        n += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", n, skipped

def exams_ics():
    """output/lichthi.ics — import vào Calendar để được nhắc tự động trước giờ thi.
    Field GetScheduleExam đã xác nhận từ dữ liệu thật (subjectCode/examDate/examTime/examRoom) nhưng parse
    ngày/giờ vẫn generic (m/d/Y ưu tiên) + dò đa biến-thể -> dòng nào không đọc được ngày thì bỏ qua."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = _exam_rows(token, campus, roll, sem)
    if not rows:
        print(t(f"📝 Chưa có lịch thi kỳ {sem} để xuất.", f"📝 No exam schedule for {sem} to export.")); return
    ics, n, skipped = build_exam_ics(rows)
    if not n:
        print(t(f"⚠️ Không đọc được ngày/giờ của {skipped} dòng lịch thi — gửi `fap exams` cho tôi để chỉnh parser.",
                f"⚠️ Couldn't parse date/time for {skipped} exam rows — share `fap exams` output to tune.")); return
    out = paths.out_dir()                         # output/ hoặc output/profiles/<tên>/ (xem core/paths.py)
    os.makedirs(out, exist_ok=True)               # thư mục có thể chưa tồn tại (checkout sạch / chưa login)
    path = os.path.join(out, "lichthi.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    tail = (f" (bỏ {skipped} dòng)" if skipped else "")
    print(t(f"✓ Ghi {n} môn thi -> output/lichthi.ics{tail}", f"✓ Wrote {n} exams -> output/lichthi.ics{tail}"))
    print(t("  Import: Google Calendar → Settings → Import & Export.", "  Import via Google Calendar settings."))
