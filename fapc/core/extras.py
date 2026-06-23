#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extras.py — tra cứu nhỏ: lịch thi, tin tức, học phí/số dư.

    fap exams   # GetScheduleExam   (cũng dùng cho `fap notify exams` + bot /exams)
    fap news    # GetTop10News
    fap fees    # GetBalance + GeFeeByRoll

Endpoint có thể RỖNG/404 với tài khoản chưa tới kỳ thi / chưa có dữ liệu — xử lý rỗng đàng hoàng.
"""
import os, datetime
from .api import creds, call, unwrap, as_list, current_semester, checksum_auth, check_auth
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
def exams_text(token, campus, roll, sem):
    http, data = call("GetScheduleExam",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem), ("Authen", token)], roll, campus)
    check_auth(http, data)        # token hết hạn -> raise rõ, KHÔNG báo nhầm "chưa có lịch thi"
    rows = as_list(data)
    if not rows:
        return t(f"📝 Chưa có lịch thi kỳ {sem} (sẽ hiện khi trường xếp lịch).",
                 f"📝 No exam schedule for {sem} yet (appears once scheduled).")
    lines = [fmt.header("📝", t(f"Lịch thi {sem}", f"Exam schedule {sem}"), str(len(rows)))]
    for r in rows:
        if isinstance(r, dict):
            lines.append("• " + " · ".join(str(v) for v in r.values() if v not in (None, "")))
        else:
            lines.append(f"• {r}")
    return "\n".join(lines)

def exams():
    token, campus, roll = creds()
    print(exams_text(token, campus, roll, current_semester(token, campus, roll)))

# ---------- TIN TỨC ----------
def news():
    token, campus, roll = creds()
    http, data = call("GetTop10News", [("campusCode", campus), ("Authen", token), ("type", "0")],
                      roll, campus, checksum_value=checksum_auth("0", campus))
    check_auth(http, data)
    rows = as_list(data)
    if not rows:
        print(t("📰 Chưa có tin tức.", "📰 No news.")); return
    rows = [{k: fmt.unescape(v) if isinstance(v, str) else v for k, v in r.items()}   # decode &#xxx; trong tin tức
            for r in rows if isinstance(r, dict)]
    print(t(f"== Tin tức ({len(rows)}) ==", f"== News ({len(rows)}) =="))
    print(fmt.table(rows))

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
    hh, mm = 7, 0
    def _clock(s):
        m = re.search(r"(\d{1,2}):(\d{2})", str(s or ""))
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            return int(m.group(1)), int(m.group(2))
        return None
    inline = _clock(dv)           # giờ nằm sẵn trong field ngày (vd '2026-06-05T13:30:00')
    if inline:
        hh, mm = inline
    else:
        for k in r:
            if str(k).lower() in ("examtime", "time", "giothi", "starttime"):
                c = _clock(r[k])
                if c: hh, mm = c; break
    s = datetime.datetime(day.year, day.month, day.day, hh, mm)
    return s, s + datetime.timedelta(hours=2)

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
        subj = r.get("subjectCode") or r.get("examSubject") or r.get("subjectName") or "Thi"
        room = r.get("examRoom") or r.get("room") or ""
        desc = " · ".join(str(v) for v in r.values() if v not in (None, ""))
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
    Field ngày/giờ thi của FAP chưa kiểm chứng (tài khoản chưa xếp lịch) -> parse generic, bỏ dòng không đọc được."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = _exam_rows(token, campus, roll, sem)
    if not rows:
        print(t(f"📝 Chưa có lịch thi kỳ {sem} để xuất.", f"📝 No exam schedule for {sem} to export.")); return
    ics, n, skipped = build_exam_ics(rows)
    if not n:
        print(t(f"⚠️ Không đọc được ngày/giờ của {skipped} dòng lịch thi — gửi `fap exams` cho tôi để chỉnh parser.",
                f"⚠️ Couldn't parse date/time for {skipped} exam rows — share `fap exams` output to tune.")); return
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output")
    os.makedirs(out, exist_ok=True)               # output/ có thể chưa tồn tại (checkout sạch / chưa login)
    path = os.path.join(out, "lichthi.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    tail = (f" (bỏ {skipped} dòng)" if skipped else "")
    print(t(f"✓ Ghi {n} môn thi -> output/lichthi.ics{tail}", f"✓ Wrote {n} exams -> output/lichthi.ics{tail}"))
    print(t("  Import: Google Calendar → Settings → Import & Export.", "  Import via Google Calendar settings."))
