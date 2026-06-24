#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""courses.py — Lớp đã đăng ký trong kỳ (GetCourseOfSemester).

Hai việc:
  1. course_id_map(): {subjectCode → courseId} để VÁ điểm thành phần cho môn mà GetStudentMark
     KHÔNG trả courseID (vd có roll chỉ thấy 4/6 môn) → GetMarkByCourse mới gọi được.
  2. `fap courses`: bảng môn/lớp/giảng viên/phòng đang học (fallback từ GetActivityStudent nếu endpoint lỗi).

GetCourseOfSemester từng trả 404 ở 1 URL dump (docs/03) → mọi nơi degrade ÊM: None/rỗng = giữ hành vi cũ.
"""
from .api import creds, call, as_list, current_semester, _err_code
from . import subjects
from ..i18n import t
from .. import fmt

_CODE_KEYS = ("subjectCode", "SubjectCode", "subjectcode")
_CID_KEYS = ("courseId", "courseID", "CourseId", "courseid", "CourseID")
_CLASS_KEYS = ("className", "ClassName", "groupName", "class")
_TEACHER_KEYS = ("teacherCode", "lecturerCode", "lecturer", "teacherName", "teacher")
_ROOM_KEYS = ("roomNo", "room", "Room")

def _first(r, keys):
    for k in keys:
        v = r.get(k)
        if v not in (None, ""):
            return v
    return None

def fetch_courses(token, campus, roll, sem):
    """GetCourseOfSemester → list lớp. None khi LỖI/404 (mạng/token/checksum) — phân biệt rỗng-thật,
    để bên gọi degrade về hành vi cũ thay vì tưởng 'không có lớp'."""
    http, data = call("GetCourseOfSemester",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll), ("semester", sem)], roll, campus)
    if http is None or http == 404 or _err_code(data) == "201":
        return None
    return as_list(data)

def course_id_map(rows):
    """THUẦN: {subjectCode → courseId} (bỏ qua dòng thiếu mã/cid). Dùng để vá điểm thành phần."""
    m = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        code, cid = _first(r, _CODE_KEYS), _first(r, _CID_KEYS)
        if code and cid is not None:
            m[str(code)] = cid
    return m

def roster(rows):
    """THUẦN: list gọn {subjectCode, className, lecturer, room} từ GetCourseOfSemester."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        code = _first(r, _CODE_KEYS)
        if not code:
            continue
        out.append({"subjectCode": str(code), "className": str(_first(r, _CLASS_KEYS) or ""),
                    "lecturer": str(_first(r, _TEACHER_KEYS) or ""), "room": str(_first(r, _ROOM_KEYS) or "")})
    return out

def roster_from_activity(sessions):
    """THUẦN fallback: gộp các buổi GetActivityStudent thành 1 dòng/môn (union phòng) khi
    GetCourseOfSemester không dùng được."""
    agg = {}
    for s in sessions or []:
        if not isinstance(s, dict):
            continue
        code = _first(s, _CODE_KEYS)
        if not code:
            continue
        e = agg.setdefault(str(code), {"subjectCode": str(code), "className": str(_first(s, _CLASS_KEYS) or ""),
                                       "lecturer": str(_first(s, _TEACHER_KEYS) or ""), "_rooms": set()})
        room = _first(s, _ROOM_KEYS)
        if room:
            e["_rooms"].add(str(room))
    out = []
    for e in agg.values():
        e["room"] = ", ".join(sorted(e.pop("_rooms")))
        out.append(e)
    return out

def courses_text(token, campus, roll, sem):
    """Bảng lớp đang học — TRẢ chuỗi (dùng cho CLI + bot). GetCourseOfSemester → roster; lỗi → GetActivityStudent."""
    subjects.load()
    rows = fetch_courses(token, campus, roll, sem)
    if rows is None or not rows:                       # 404/lỗi/rỗng → thử dựng từ TKB
        from .schedule import fetch_sessions
        items = roster_from_activity(fetch_sessions(token, campus, roll, sem))
    else:
        items = roster(rows)
    if not items:
        return t("📋 Chưa lấy được danh sách lớp.", "📋 Couldn't load your class roster.")
    out = [fmt.header("📋", t(f"Lớp đang học · {sem}", f"My classes · {sem}"),
                      t(f"{len(items)} lớp", f"{len(items)} classes"))]
    for c in items:
        bits = [subjects.label(c["subjectCode"])]
        if c.get("className"): bits.append(c["className"])
        if c.get("lecturer"):  bits.append("👤 " + c["lecturer"])
        if c.get("room"):      bits.append("📍 " + c["room"])
        out.append("• " + "  ·  ".join(bits))
    return "\n".join(out)

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print(courses_text(token, campus, roll, sem))
