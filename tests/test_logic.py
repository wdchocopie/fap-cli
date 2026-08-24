#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm thử OFFLINE cho logic thuần (không gọi mạng) · Offline unit tests for pure logic.

Chạy · Run:
    python tests/test_logic.py        # không cần pytest · no pytest needed
    python -m pytest tests/           # nếu có pytest · if pytest installed

Chỉ test các hàm KHÔNG gọi API: parse ngày/giờ, dựng .ics, GPA, mô phỏng whatif,
gom lịch tuần, in bảng transcript, digest thông báo.
"""
import os, sys, io, contextlib, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fapc.core.schedule import parse_session, build_ics
from fapc.core.grades import _gpa
from fapc.core.whatif import _split, needed_average
from fapc.app.dashboard import _week_bounds, _day_lines
from fapc.fmt import room as fmt_room, safe_float
from fapc.app.notify import _day_digest, _week_digest

# ---- fixtures (đúng field GetActivityStudent thật) ----
def _sess(date, slot_time, code, room="BE-301", online="false", slot="1"):
    return {"date": date, "slotTime": slot_time, "subjectCode": code, "roomNo": room,
            "isOnline": online, "lecturer": "GV", "slot": slot, "groupName": "IA1900", "sessionNo": "3"}

MON = _sess("06/15/2026", "(07:30 - 09:00)", "EXE101")          # T2 15/06/2026
MON2 = _sess("06/15/2026", "(09:10 - 10:40)", "HOD402")          # cùng ngày, muộn hơn
WED = _sess("06/17/2026", "(13:00 - 15:00)", "IAP301", online="true")  # T4, online
BAD = {"date": "", "slotTime": ""}                               # thiếu -> None


def test_parse_session_unambiguous():
    start, end, amb = parse_session(MON)
    assert start == datetime.datetime(2026, 6, 15, 7, 30)
    assert end == datetime.datetime(2026, 6, 15, 9, 0)
    assert amb is False           # 15 > 12 nên không mơ hồ

def test_parse_session_iso_and_overnight():
    s = parse_session(_sess("2026-06-15", "(23:30 - 00:30)", "X"))
    assert s is not None
    start, end, _ = s
    assert end > start and end.day == 16          # qua nửa đêm -> +1 ngày

def test_parse_session_none_when_missing():
    assert parse_session(BAD) is None
    assert parse_session({"date": "06/15/2026", "slotTime": "no-time"}) is None

def test_build_ics_counts():
    ics, n, skipped, amb = build_ics([MON, MON2, WED, BAD])
    assert n == 3 and skipped == 1
    assert ics.count("BEGIN:VEVENT") == 3
    assert "END:VCALENDAR" in ics

def test_gpa():
    assert _gpa([{"averageMark": "8.0"}, {"averageMark": "0.0"}, {"averageMark": "6.0"}]) == 7.0
    assert _gpa([{"averageMark": "0.0"}]) is None     # chưa có điểm
    assert _gpa([]) is None

def test_whatif_split():
    rows = [{"subjectCode": "A", "averageMark": "8.0"},
            {"subjectCode": "B", "averageMark": "6.0"},
            {"subjectCode": "C", "averageMark": "0.0"}]
    graded, sg, remaining = _split(rows)
    assert len(graded) == 2 and sg == 14.0 and remaining == 1

def test_whatif_needed_average():
    # sum_graded=14, n_total=3, remaining=1
    assert needed_average(8, 14.0, 3, 1) == 10.0          # vừa khít thang 10
    assert needed_average(9, 14.0, 3, 1) == 13.0          # > 10 -> caller báo không khả thi
    assert needed_average(8, 0.0, 4, 4) == 8.0            # account chưa có điểm: cần đúng target
    assert needed_average(8, 14.0, 3, 0) is None          # không còn môn nào

def test_week_bounds():
    mon, sun = _week_bounds(datetime.date(2026, 6, 17))   # T4
    assert mon == datetime.date(2026, 6, 15) and sun == datetime.date(2026, 6, 21)
    mon2, _ = _week_bounds(datetime.date(2026, 6, 15))    # đầu tuần
    assert mon2 == datetime.date(2026, 6, 15)

def test_day_lines_sorted_and_filtered():
    lines = _day_lines([MON2, MON, WED], datetime.date(2026, 6, 15))
    assert len(lines) == 2
    assert "EXE101" in lines[0] and "HOD402" in lines[1]   # 07:30 trước 09:10

def test_room_online_vs_physical():
    assert fmt_room(WED) == "💻 Online"
    assert fmt_room(MON) == "📍 BE-301"
    assert safe_float("8.5") == 8.5 and safe_float(None) == 0.0 and safe_float("x") == 0.0

def test_day_digest_text():
    msg = _day_digest([MON, MON2], datetime.date(2026, 6, 15))
    assert "15/06/2026" in msg and "EXE101" in msg and "HOD402" in msg
    empty = _day_digest([MON], datetime.date(2026, 6, 16))
    assert "🎉" in empty                                   # ngày không có buổi

def test_week_digest_text():
    msg = _week_digest([MON, MON2, WED], datetime.date(2026, 6, 17))
    assert "EXE101" in msg and "IAP301" in msg
    assert "15/06" in msg

# ---- render end-to-end (monkeypatch mạng, không gọi API) ----
def _cap(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()

def test_status_and_week_render_offline():
    import fapc.app.dashboard as D
    sessions = [MON, MON2, WED]
    D.creds = lambda: ("tok", "FPTU", "HE190000")
    D.current_semester = lambda *a, **k: "Summer2026"
    D.fetch_sessions = lambda *a, **k: sessions
    D.fetch_marks = lambda *a, **k: [{"subjectCode": "A", "averageMark": "8.0"},
                                     {"subjectCode": "B", "averageMark": "0.0"}]
    D.fetch_att = lambda *a, **k: [{"subjectCode": "A", "attendance": "100"},
                                   {"subjectCode": "B", "attendance": "60"}]
    # week() nay tra mốc kỳ qua GetSemester (để in 'Tuần N/M') -> PHẢI stub, nếu không bộ test
    # "offline" bắn request thật tới api.fpt.edu.vn (và bot chạy selftest mỗi lần /update!).
    D.fetch_semesters = lambda *a, **k: [{"semesterName": "Summer2026",
                                          "startDate": "2026-05-04", "endDate": "2026-08-30"}]
    D._ident = lambda: ("Nguyen Van A", "a@fpt.edu.vn")
    D._vn_now = lambda: datetime.datetime(2026, 6, 15, 8, 0)     # cố định -> hôm nay = T2 15/06
    out = _cap(D.status)
    assert "EXE101" in out                 # lịch hôm nay
    assert "60%" in out and "⚠️" in out     # môn B chuyên cần 60% -> cảnh báo
    wk = _cap(lambda: D.week(None))
    assert "EXE101" in wk and "IAP301" in wk
    assert _cap(lambda: D.week("next")).strip() != ""   # tuần sau không crash

def test_whatif_render_offline():
    import fapc.core.whatif as W
    W.creds = lambda: ("t", "FPTU", "HE1")
    W.current_semester = lambda *a, **k: "Summer2026"
    W.fetch_marks = lambda *a, **k: [{"subjectCode": "A", "averageMark": "8.0"},
                                     {"subjectCode": "B", "averageMark": "0.0"}]
    proj = _cap(lambda: W.run(None))
    assert "GPA" in proj
    tgt = _cap(lambda: W.run("8"))
    assert "8" in tgt
    _cap(lambda: W.run("xyz"))             # target rác -> rơi về bảng dự kiến, không crash

def test_transcript_render_offline():
    import fapc.core.transcript as T
    T.creds = lambda: ("t", "FPTU", "HE1")
    T.fetch = lambda *a, **k: []           # rỗng (tài khoản chưa hoàn tất kỳ)
    assert "Chưa" in _cap(T.report) or "No academic" in _cap(T.report)
    T.fetch = lambda *a, **k: [{"subjectCode": "PRF192", "grade": "8.0", "credit": "3"}]
    assert "PRF192" in _cap(T.report)

def test_botcore_help_and_unknown():
    import fapc.app.bot_core as B
    assert "FAP bot" in B.handle("/help")
    assert "FAP bot" in B.handle("")                 # rỗng -> help
    u = B.handle("/khong-co-lenh")
    assert "không rõ" in u or "Unknown" in u

def test_botcore_commands_offline():
    import fapc.app.bot_core as B
    B.creds = lambda: ("tok", "FPTU", "HE190000")
    B.current_semester = lambda *a, **k: "Summer2026"
    B.fetch_sessions = lambda *a, **k: [MON, MON2, WED]
    B.fetch_marks = lambda *a, **k: [{"subjectCode": "A", "averageMark": "8.0", "status": "Passed"},
                                     {"subjectCode": "B", "averageMark": "0.0", "status": "Not Passed"}]
    B.fetch_att = lambda *a, **k: [{"subjectCode": "A", "attendance": "100"},
                                   {"subjectCode": "B", "attendance": "60"}]
    B._vn_now = lambda: datetime.datetime(2026, 6, 15, 8, 0)   # cố định -> hôm nay = T2 15/06
    assert "EXE101" in B.handle("today")
    assert "EXE101" in B.handle("/week") and "IAP301" in B.handle("/week")
    assert "GPA" in B.handle("grades")
    assert "60%" in B.handle("attendance") and "⚠️" in B.handle("attendance")
    assert "B" in B.handle("banrisk")                          # B 60% -> nguy cơ
    assert "GPA" in B.handle("whatif")                         # bảng dự kiến
    assert "8" in B.handle("whatif", "8")                      # cần TB 8 để đạt GPA 8
    assert "GPA" in B.handle("status")


def test_notify_routes_to_botcore():
    import fapc.app.notify as N, fapc.app.bot_core as B
    B.creds = lambda: ("t", "FPTU", "HE1")
    B.current_semester = lambda *a, **k: "Summer2026"
    B.fetch_att = lambda *a, **k: [{"subjectCode": "B", "attendance": "60"}]
    cap = {}
    N.push = lambda text: (cap.__setitem__("text", text), ["Telegram"])[1]
    _cap(lambda: N.run("banrisk"))                  # notify đẩy điểm danh/cấm thi qua bot_core
    assert "B" in cap.get("text", "") and "60%" in cap["text"]
    cap.clear()
    _cap(lambda: N.run("khong-co"))                 # lệnh lạ -> KHÔNG push
    assert "text" not in cap


def test_send_checks_http_status():
    """Regression: HTTP 4xx KHÔNG được báo 'đã gửi' (requests.post không ném lỗi cho 4xx)."""
    import fapc.app.notify as N
    from fapc import config as C
    class _R:
        def __init__(s, code, text="", js=None): s.status_code = code; s.ok = 200 <= code < 300; s.text = text; s._js = js
        def json(s):
            if s._js is None: raise ValueError()
            return s._js
    orig = N.requests.post
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            C.TELEGRAM_TOKEN, C.TELEGRAM_CHAT = "x", "1"
            N.requests.post = lambda *a, **k: _R(200, js={"ok": True})
            assert N._telegram("hi") is True
            N.requests.post = lambda *a, **k: _R(400, '{"ok":false}', {"ok": False})
            assert N._telegram("hi") is False                  # 400 -> KHÔNG thành công
            C.DISCORD_WEBHOOK_URL = "http://x"
            N.requests.post = lambda *a, **k: _R(204)
            assert N._discord("hi") is True                    # webhook OK = 204
            N.requests.post = lambda *a, **k: _R(404, "Unknown Webhook")
            assert N._discord("hi") is False                   # webhook xóa -> False
    finally:
        N.requests.post = orig


def test_attendwatch_compute():
    import fapc.app.attendwatch as W
    assert W._recorded({"attendanceStatus": "Present"}) is True
    assert W._recorded({"attendanceStatus": "Future"}) is False
    assert W._fmt_date("2026-06-15T00:00:00") == "15/06/2026"

    subj2 = [{"subjectCode": "EXE101", "groupName": "G1", "numberOfTakenAttendances": 2}]
    det = [{"scheduleID": 1, "date": "2026-06-01T00:00:00", "slot": 1, "roomNo": "B1", "attendanceStatus": "Present"},
           {"scheduleID": 2, "date": "2026-06-08T00:00:00", "slot": 1, "roomNo": "B1", "attendanceStatus": "Present"},
           {"scheduleID": 3, "date": "2026-06-15T00:00:00", "slot": 1, "roomNo": "B1", "attendanceStatus": "Future"}]

    # Lần đầu: KHÔNG báo dồn lịch sử, chỉ ghi nhận trạng thái
    events, state, first = W.compute(subj2, lambda s, g: det, {})
    assert first is True and events == []
    assert state["EXE101"]["taken"] == 2 and set(state["EXE101"]["seen"]) == {"1", "2"}

    # Không đổi (taken vẫn 2) -> KHÔNG tải chi tiết (gate rẻ), không event
    def _boom(s, g): raise AssertionError("không được tải chi tiết khi số buổi không đổi")
    ev2, _, f2 = W.compute(subj2, _boom, state)
    assert f2 is False and ev2 == []

    # Buổi 3 vừa được điểm danh: Future -> Present, taken 2->3
    subj3 = [{"subjectCode": "EXE101", "groupName": "G1", "numberOfTakenAttendances": 3}]
    det3 = det[:2] + [{"scheduleID": 3, "date": "2026-06-15T00:00:00", "slot": 1, "roomNo": "B1", "attendanceStatus": "Present"}]
    ev3, st3, f3 = W.compute(subj3, lambda s, g: det3, state)
    assert len(ev3) == 1 and str(ev3[0][1]["scheduleID"]) == "3"
    assert ev3[0][1]["attendanceStatus"] == "Present"
    assert set(st3["EXE101"]["seen"]) == {"1", "2", "3"}

def test_attendwatch_absent_only():
    import fapc.app.attendwatch as W
    assert W._is_present({"attendanceStatus": "Present"}) is True
    assert W._is_present({"attendanceStatus": "Absent"}) is False
    ev = [("A", {"attendanceStatus": "Present"}), ("B", {"attendanceStatus": "Absent"}),
          ("C", {"attendanceStatus": "Late"})]
    assert len(W._to_push(ev, False)) == 3                # mặc định: gửi hết
    assert [e[0] for e in W._to_push(ev, True)] == ["B", "C"]   # chỉ-báo-vắng: bỏ Present


def test_attendance_empty_not_at_risk():
    from fapc.core.attendance import _pct, _at_risk
    assert _pct({"attendance": "100"}) == 100.0 and _pct({"attendance": "60"}) == 60.0
    assert _pct({"attendance": ""}) is None and _pct({"attendance": None}) is None and _pct({}) is None
    assert _at_risk({"attendance": "60"}) is True       # 60% < 80 -> nguy cơ
    assert _at_risk({"attendance": "100"}) is False
    assert _at_risk({"attendance": ""}) is False        # CHƯA có dữ liệu -> KHÔNG gắn nguy cơ (bug đã sửa)
    assert _at_risk({"attendance": "0"}) is True        # 0% THẬT vẫn là nguy cơ

def test_auth_redact():
    from fapc.core.auth import _redact
    r = _redact({"authenKey": "s", "email": "a@b.com", "data": [{"token": "x", "ok": 1}], "campus": "FPTU"})
    assert r["authenKey"] == "***REDACTED***" and r["email"] == "***REDACTED***"
    assert r["data"][0]["token"] == "***REDACTED***" and r["data"][0]["ok"] == 1   # khóa không nhạy cảm giữ nguyên
    assert r["campus"] == "FPTU"


def test_api_cache():
    import os, fapc.core.api as A
    n = {"c": 0}
    class _R:
        status_code = 200
        def json(self): return {"code": "200", "data": [1, 2]}
    orig = A.requests.get
    try:
        A._CACHE.clear(); os.environ["FAP_CACHE_MIN"] = "5"
        A.requests.get = lambda *a, **k: (n.__setitem__("c", n["c"] + 1), _R())[1]
        r1 = A.call("X", [("a", "1")], "HE1", "FPTU", checksum_value=False)
        r2 = A.call("X", [("a", "1")], "HE1", "FPTU", checksum_value=False)
        assert r1 == r2 and n["c"] == 1            # lần 2 lấy từ cache (không gọi mạng)
        os.environ["FAP_CACHE_MIN"] = "0"
        A.call("X", [("a", "1")], "HE1", "FPTU", checksum_value=False)
        assert n["c"] == 2                          # tắt cache -> gọi lại
    finally:
        A.requests.get = orig; os.environ.pop("FAP_CACHE_MIN", None); A._CACHE.clear()


def _raises_exit(fn):
    try: fn(); return False
    except SystemExit: return True

def test_exams_text_raises_on_expired_token():
    """H2: endpoint phụ (exams) cũng phải báo token hết hạn, không nói nhầm 'chưa có lịch thi'."""
    import fapc.core.extras as E
    E.call = lambda *a, **k: (200, {"code": "201", "message": "Token invalid"})
    assert _raises_exit(lambda: E.exams_text("t", "FPTU", "HE1", "Summer2026"))
    E.call = lambda *a, **k: (200, {"code": "200", "data": []})       # rỗng HỢP LỆ -> không raise
    assert "Chưa có lịch thi" in E.exams_text("t", "FPTU", "HE1", "Summer2026")

def test_attendwatch_detail_failure_keeps_watermark():
    """H3: chi tiết lấy HỎNG (None) -> KHÔNG dời mốc, KHÔNG nuốt buổi (dò lại lượt sau)."""
    import fapc.app.attendwatch as W
    subj2 = [{"subjectCode": "EXE101", "groupName": "G1", "numberOfTakenAttendances": 2}]
    det = [{"scheduleID": 1, "date": "2026-06-01T00:00:00", "slot": 1, "attendanceStatus": "Present"},
           {"scheduleID": 2, "date": "2026-06-08T00:00:00", "slot": 1, "attendanceStatus": "Present"}]
    _, state, _ = W.compute(subj2, lambda s, g: det, {})              # baseline: taken=2, seen={1,2}
    subj3 = [{"subjectCode": "EXE101", "groupName": "G1", "numberOfTakenAttendances": 3}]
    ev, st, first = W.compute(subj3, lambda s, g: None, state)        # số buổi tăng nhưng fetch HỎNG
    assert first is False and ev == []                                # không báo bừa
    assert st["EXE101"]["taken"] == 2 and set(st["EXE101"]["seen"]) == {"1", "2"}   # GIỮ mốc cũ -> lượt sau dò lại

def test_whatif_guaranteed_boundary_need_zero():
    """L1: need == 0 cũng là 'đã chắc chắn đạt' (không phải 'cần TB 0.0/10')."""
    from fapc.core.whatif import needed_average
    assert needed_average(6, 18.0, 3, 1) == 0.0      # sg=18, target*n_total=18 -> need=0 (giáp ranh)
    import fapc.core.whatif as W
    W.creds = lambda: ("t", "FPTU", "HE1")
    W.current_semester = lambda *a, **k: "Summer2026"
    W.fetch_marks = lambda *a, **k: [{"subjectCode": "A", "averageMark": "9.0"},
                                     {"subjectCode": "B", "averageMark": "9.0"},
                                     {"subjectCode": "C", "averageMark": "0.0"}]
    out = _cap(lambda: W.run("6"))                   # need==0 -> nhánh 'đã chắc chắn đạt'
    assert "chắc chắn" in out or "guaranteed" in out

def test_check_auth_expired_vs_checksum_vs_ok():
    from fapc.core.api import check_auth
    # PROBE THẬT: token sai/checksum sai đều = HTTP 200 + code 201, phân biệt bằng message
    assert _raises_exit(lambda: check_auth(401, {}))                                   # HTTP 401
    assert _raises_exit(lambda: check_auth(200, {"code": "201", "message": "Token invalid"}))
    assert _raises_exit(lambda: check_auth(200, {"code": "201", "message": "Thông tin checksum không chính xác"}))
    assert not _raises_exit(lambda: check_auth(200, {"code": "200", "data": []}))      # rỗng HỢP LỆ
    assert not _raises_exit(lambda: check_auth(200, {"data": []}))                     # không có code -> bỏ qua

def test_is_checksum_error():
    from fapc.core.api import _is_checksum_error
    assert _is_checksum_error((200, {"code": "201", "message": "Thông tin checksum không chính xác"})) is True
    assert _is_checksum_error((200, {"code": "201", "message": "Token invalid"})) is False   # token, KHÔNG phải checksum
    assert _is_checksum_error((200, {"code": "200", "data": []})) is False
    assert _is_checksum_error((None, "Lỗi mạng")) is False

def test_call_retries_on_checksum_error():
    """call() tự thử lại ±1h khi lỗi checksum (lệch giờ đầu giờ) — chỉ với checksum mặc định."""
    import fapc.core.api as A
    n = {"c": 0}
    class _R:
        def __init__(self, js): self.status_code = 200; self._js = js
        def json(self): return self._js
    def fake_get(url, **k):
        n["c"] += 1
        if n["c"] == 1:                    # lần đầu: lỗi checksum
            return _R({"code": "201", "message": "Thông tin checksum không chính xác"})
        return _R({"code": "200", "data": [1]})    # lần retry (giờ +1): OK
    orig = A.requests.get
    try:
        A._CACHE.clear()
        A.requests.get = fake_get
        http, data = A.call("GetStudentMark", [("a", "1")], "HE1", "FPTU")   # checksum mặc định
        assert http == 200 and data.get("code") == "200" and n["c"] == 2     # đã retry đúng 1 lần
    finally:
        A.requests.get = orig; A._CACHE.clear()

def test_fmt_table_generic():
    from fapc.fmt import table
    s = table([{"a": "1", "b": "22"}, {"a": "333", "b": "4"}])
    assert "a" in s and "333" in s and "22" in s        # có header + mọi ô
    assert table([]) == ""                               # rỗng -> chuỗi rỗng
    assert "raw-row" in table(["raw-row"])               # non-dict -> in thô, không lỗi
    assert table([None]) == ""                           # lọc None

def test_grades_detail_text_offline():
    import fapc.core.grades as G, fapc.core.courses as C
    C.fetch_courses = lambda *a, **k: []                  # P7: không vá thêm môn trong test này (cmap rỗng)
    G.fetch_marks = lambda *a, **k: [{"subjectCode": "PRF192", "courseID": 11},
                                     {"subjectCode": "MAE101", "courseID": None}]
    # courseID 11 -> 1 thành phần (field 'course*' bị lọc); None -> chưa có
    G.call = lambda *a, **k: (200, {"data": [{"courseID": 11, "item": "Assignment", "value": "8.0", "weight": "20%"}]})
    txt = G.detail_text("t", "FPTU", "HE1", "Summer2026")
    assert "PRF192" in txt and "Assignment" in txt and "8.0" in txt and "courseID" not in txt
    assert "MAE101" in txt                                # môn không courseID vẫn liệt kê (chưa có TP)
    # LỖI tải (code 201) != rỗng thật -> phải hiện cảnh báo, KHÔNG nói 'chưa có điểm'
    G.fetch_marks = lambda *a, **k: [{"subjectCode": "PRF192", "courseID": 11}]
    G.call = lambda *a, **k: (200, {"code": "201", "message": "Token invalid", "data": []})
    err = G.detail_text("t", "FPTU", "HE1", "Summer2026")
    assert ("lỗi tải" in err or "failed to load" in err) and "chưa có điểm thành phần" not in err

def test_grades_components_accepts_dict_shape():
    """GetMarkByCourse có thể trả dict (không phải list) -> KHÔNG được âm thầm bỏ (as_list cũ làm thế)."""
    import fapc.core.grades as G
    # dict chứa mảng con 'details' -> lấy mảng đó
    G.call = lambda *a, **k: (200, {"data": {"average": "7", "details": [{"item": "Lab", "value": "7.0"}]}})
    rows = G._components("t", "FPTU", "HE1", 11, "PRF192")
    assert rows and rows[0].get("item") == "Lab" and rows[0].get("value") == "7.0"
    # dict toàn scalar -> coi cả dict là 1 dòng
    G.call = lambda *a, **k: (200, {"data": {"item": "Final", "value": "9.0"}})
    rows2 = G._components("t", "FPTU", "HE1", 11, "PRF192")
    assert rows2 and rows2[0].get("item") == "Final"
    # rỗng thật -> []
    G.call = lambda *a, **k: (200, {"data": []})
    assert G._components("t", "FPTU", "HE1", 11, "PRF192") == []
    assert G._components("t", "FPTU", "HE1", None) == []   # không courseID

def test_botcore_all_offline():
    import fapc.app.bot_core as B, fapc.core.grades as G, fapc.core.extras as E, fapc.core.courses as C
    C.fetch_courses = lambda *a, **k: None                # P7: GetCourseOfSemester không dùng được -> degrade
    marks = lambda *a, **k: [{"subjectCode": "A", "averageMark": "8.0", "status": "Passed", "courseID": None}]
    B.creds = lambda: ("tok", "FPTU", "HE190000")
    B.current_semester = lambda *a, **k: "Summer2026"
    B.fetch_sessions = lambda *a, **k: [MON, MON2, WED]
    B.fetch_marks = marks
    G.fetch_marks = marks                                 # detail_text dùng tên trong module grades
    B.fetch_att = lambda *a, **k: [{"subjectCode": "A", "attendance": "100"}]
    B._vn_now = lambda: datetime.datetime(2026, 6, 15, 8, 0)
    E.call = lambda *a, **k: (200, {"data": []})          # exams_text dùng tên trong module extras -> rỗng
    out = B.handle("all")
    assert "EXE101" in out and "GPA" in out and "Điểm danh" in out   # gộp nhiều mục

def test_botcore_handle_catches_systemexit():
    import fapc.app.bot_core as B
    def _boom():
        raise SystemExit("⚠️ Token FAP có thể đã hết hạn")
    B.creds = _boom                                       # mô phỏng token hết hạn
    msg = B.handle("status")
    assert "hết hạn" in msg                               # trả LỜI, KHÔNG sập bot

def test_gradewatch_compute():
    import fapc.app.gradewatch as G
    marks = [{"subjectCode": "EXE101", "courseID": 1, "averageMark": "0.0"}]
    ev, st, first = G.compute(marks, lambda s, c: [{"component": "Assignment", "value": ""}], {})
    assert first is True and ev == []                       # baseline: đầu điểm chưa có giá trị
    ev2, st2, f2 = G.compute(marks, lambda s, c: [{"component": "Assignment", "value": "8.5"}], st)
    assert f2 is False and any(e["item"] == "Assignment" and e["value"] == "8.5" for e in ev2)   # vừa có điểm -> báo
    ev3, _, _ = G.compute(marks, lambda s, c: [{"component": "Assignment", "value": "8.5"}], st2)
    assert ev3 == []                                        # không đổi -> không báo lại
    ev4, st4, _ = G.compute(marks, lambda s, c: None, st2)  # chi tiết HỎNG -> giữ mốc, không báo bừa
    assert ev4 == [] and st4["EXE101"]["comps"]["Assignment"] == "8.5"

def test_gradewatch_final_mark_event():
    import fapc.app.gradewatch as G
    m0 = [{"subjectCode": "MAE101", "courseID": 2, "averageMark": "0.0"}]
    _, st, _ = G.compute(m0, lambda s, c: [], {})
    m1 = [{"subjectCode": "MAE101", "courseID": 2, "averageMark": "9.0"}]
    ev, _, _ = G.compute(m1, lambda s, c: [], st)
    assert any(e["item"] is None and e["value"] == "9.0" for e in ev)   # điểm tổng kết 0.0 -> 9.0

def test_gradewatch_render_events():
    """Thông báo điểm mới ĐẸP: gom theo MÔN, sort TỰ NHIÊN (LAB 2 trước LAB 10), điểm tổng kết ở cuối khối."""
    from fapc.app.gradewatch import render_events, _natkey
    assert _natkey("LAB 2") < _natkey("LAB 10")            # so số, KHÔNG so chuỗi ('10' < '2' theo chuỗi)
    ev = [{"subj": "X", "item": "LAB 10", "value": "9"},
          {"subj": "X", "item": "LAB 2", "value": "8"},
          {"subj": "X", "item": None, "value": "8.5"},       # điểm tổng kết môn X
          {"subj": "Y", "item": "Final Exam", "value": "7"}]
    out = render_events(ev)
    assert "📘 X" in out and "📘 Y" in out
    assert out.index("📘 X") < out.index("📘 Y")            # giữ thứ tự môn xuất hiện
    assert out.index("LAB 2") < out.index("LAB 10")         # sort tự nhiên trong 1 môn
    assert out.index("LAB 10") < out.index("8.5")           # điểm tổng kết ở CUỐI khối môn
    assert render_events([]) == ""

def test_weighted_gpa():
    from fapc.core.transcript import _weighted_gpa
    assert _weighted_gpa([{"averageMark": "8.0", "credit": "3"},
                          {"averageMark": "6.0", "credit": "1"}]) == 7.5    # (8*3+6*1)/4
    assert _weighted_gpa([{"averageMark": "0.0", "credit": "3"}]) is None   # chưa có điểm
    assert _weighted_gpa([]) is None

def test_week_exact_text_offline():
    """TKB-theo-tuần render generic (shape chưa kiểm chứng): group theo ngày, sort đúng, không sập."""
    from fapc.app.dashboard import week_exact_text
    rows = [{"date": "06/24/2026", "slot": "2", "subjectCode": "CES202", "roomNo": "BE-305"},
            {"date": "06/22/2026", "slot": "1", "subjectCode": "IAP301", "room": "BE-304", "lecturer": "GV"}]
    txt = week_exact_text(rows, 25, 2026)
    assert "IAP301" in txt and "CES202" in txt and "BE-304" in txt and "TKB tuần 25/2026" in txt
    assert txt.index("IAP301") < txt.index("CES202")          # 22/06 trước 24/06 (sort theo ngày)
    empty = week_exact_text([], 25, 2026)
    assert "không có buổi" in empty or "no sessions" in empty   # rỗng -> thông báo, không sập

def test_fmt_unescape():
    from fapc.fmt import unescape
    assert unescape("Nguy&#7877;n V&#259;n A") == "Nguyễn Văn A"   # &#xxx; -> ký tự tiếng Việt
    assert unescape("Ph&#242;ng &#272;T &quot;A&quot;") == 'Phòng ĐT "A"'
    assert unescape(None) == "" and unescape("  x  ") == "x"

def test_applications_text_offline():
    import fapc.core.extras as E
    E.fetch_applications = lambda *a, **k: [
        {"name": "Đơn A", "createDate": "16/09/2023", "processNote": "Ph&#242;ng &#272;T đã nhận"},
        {"name": "Đơn B", "createDate": "05/03/2026", "processNote": ""}]
    txt = E.applications_text("t", "FPTU", "HE1")
    assert "Đơn A" in txt and "Đơn B" in txt and "Phòng ĐT đã nhận" in txt   # decode entity
    assert txt.index("Đơn B") < txt.index("Đơn A")                           # mới nhất (2026) trước
    E.fetch_applications = lambda *a, **k: []
    assert "Chưa có đơn" in E.applications_text("t", "FPTU", "HE1") or "No applications" in E.applications_text("t", "FPTU", "HE1")

def test_profile_text_offline():
    import fapc.core.extras as E
    E.fetch_profile = lambda *a, **k: [{"fullname": "Nguyễn Văn A", "rollNumber": "HE190000",
        "email": "x@gmail.com", "dateOfBirth": "2004-09-15T00:00:00", "gender": True, "statusCode": "HD", "iDCard": ""}]
    txt = E.profile_text("t", "FPTU", "HE1")
    assert "Nguyễn Văn A" in txt and "HE190000" in txt and "15/09/2004" in txt and "Nam" in txt
    assert "CCCD" not in txt                                                 # field rỗng -> KHÔNG hiện

def test_default_semester_by_date():
    """Học kỳ mặc định suy theo ngày -> đúng cho MỌI sinh viên/mọi kỳ (không hardcode 1 kỳ)."""
    from fapc.core.api import default_semester
    assert default_semester(datetime.datetime(2026, 1, 15)) == "Spring2026"
    assert default_semester(datetime.datetime(2026, 4, 30)) == "Spring2026"   # ranh giới T4
    assert default_semester(datetime.datetime(2026, 5, 1)) == "Summer2026"    # ranh giới T5
    assert default_semester(datetime.datetime(2026, 8, 31)) == "Summer2026"
    assert default_semester(datetime.datetime(2026, 9, 1)) == "Fall2026"
    assert default_semester(datetime.datetime(2027, 12, 31)) == "Fall2027"

def test_campuses_text_offline():
    import fapc.core.extras as E
    E.call = lambda *a, **k: (200, {"code": "200", "data": [{"campusCode": "FPTU", "campusName": "Hoa Lac"},
                                                            {"campusCode": "CT", "campusName": "Can Tho"}]})
    txt = E.campuses_text()
    assert "FPTU" in txt and "Hoa Lac" in txt and "CT" in txt
    E.call = lambda *a, **k: (None, "Lỗi mạng")          # mất mạng -> thông báo, không sập
    assert "campus" in E.campuses_text().lower()

def test_current_semester_ignores_bad_dates():
    """Robustness: 1 kỳ có ngày lỗi KHÔNG được làm hỏng tự-dò học kỳ (FAP trả ~28 kỳ, 1 lỗi không kéo sập)."""
    import io, contextlib, fapc.core.api as A
    orig_sem = os.environ.get("FAP_SEMESTER"); orig_get = A.requests.get
    now = A._vn_now().replace(tzinfo=None)
    good = {"semesterName": "ProbeSem", "startDate": (now - datetime.timedelta(days=5)).isoformat(),
            "endDate": (now + datetime.timedelta(days=30)).isoformat()}
    bad = {"semesterName": "Bad", "startDate": "NOT-A-DATE", "endDate": "NOT-A-DATE"}
    class _R:
        status_code = 200
        def __init__(s, d): s._d = d
        def json(s): return {"message": "ok", "code": "200", "data": s._d}
    try:
        os.environ.pop("FAP_SEMESTER", None); A._CACHE.clear()
        A.requests.get = lambda url, **k: _R([bad, good])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sem = A.current_semester("tok", "FPTU", "HE1")
        assert sem == "ProbeSem", f"phải bỏ qua kỳ ngày-lỗi và tìm ra kỳ hợp lệ, got {sem!r}"
    finally:
        A.requests.get = orig_get; A._CACHE.clear()
        if orig_sem is None: os.environ.pop("FAP_SEMESTER", None)
        else: os.environ["FAP_SEMESTER"] = orig_sem

def test_exam_dt_parser():
    from fapc.core.extras import _exam_dt
    assert _exam_dt({"examDate": "2026-06-25T13:30:00"})[0].hour == 13          # giờ nằm trong field ngày
    r = _exam_dt({"examDate": "06/25/2026", "examTime": "09:15"}); assert (r[0].hour, r[0].minute) == (9, 15)
    assert _exam_dt({"examDate": "06/25/2026"})[0].hour == 7                    # không có giờ -> mặc định 07:00
    assert _exam_dt({"examDate": "06/25/2026", "examTime": "99:99"})[0].hour == 7   # giờ rác -> mặc định
    assert _exam_dt({"examDate": "06/25/2026", "slot": "P1:02"})[0].hour == 7       # 'slot' KHÔNG phải giờ thi
    assert _exam_dt({"examRoom": "X"}) is None                                  # thiếu ngày -> None

def test_watch_state_corrupt_quarantine():
    """State HỎNG -> phải đổi tên .corrupt. (Bug: json.load(open()) rò handle -> os.replace fail trên Windows.)"""
    import tempfile, io, contextlib
    import fapc.app.gradewatch as G, fapc.app.attendwatch as A
    d = tempfile.mkdtemp()
    for mod, name in [(G, "g.json"), (A, "a.json")]:
        mod.STATE = os.path.join(d, name)
        with open(mod.STATE, "w", encoding="utf-8") as f:
            f.write("{ broken json !!!")
        with contextlib.redirect_stdout(io.StringIO()):
            st = mod._load_state()
        assert st == {}, f"{name}: state hỏng phải trả {{}}"
        assert os.path.exists(mod.STATE + ".corrupt"), f"{name}: phải cô lập file hỏng -> .corrupt"

def test_build_exam_ics():
    from fapc.core.extras import build_exam_ics
    rows = [{"subjectCode": "IAP301", "examDate": "06/25/2026", "examTime": "07:30", "examRoom": "BE-101"},
            {"subjectCode": "X", "examRoom": "Z"}]                    # thiếu ngày -> skip
    ics, n, skipped = build_exam_ics(rows)
    assert n == 1 and skipped == 1
    assert "SUMMARY:[Thi] IAP301" in ics and "DTSTART;TZID=Asia/Ho_Chi_Minh:20260625T073000" in ics
    assert "TRIGGER:-P1D" in ics and ics.count("BEGIN:VEVENT") == 1   # có nhắc trước 1 ngày
    assert build_exam_ics([])[1] == 0                                 # rỗng -> 0 sự kiện, không lỗi

def test_gpa_text_offline():
    import fapc.core.transcript as T
    T.fetch = lambda *a, **k: [{"subjectCode": "PRF192", "averageMark": "8.0", "credit": "3", "semesterName": "Fall2025"},
                               {"subjectCode": "MAE101", "averageMark": "9.0", "credit": "3", "semesterName": "Fall2025"}]
    txt = T.gpa_text("t", "FPTU", "HE1")
    assert "8.5" in txt and "Fall2025" in txt                         # (8*3+9*3)/6 = 8.5
    T.fetch = lambda *a, **k: []
    assert "Chưa có GPA" in T.gpa_text("t", "FPTU", "HE1") or "No cumulative" in T.gpa_text("t", "FPTU", "HE1")

def test_notifications_text_offline():
    import fapc.core.extras as E
    E.fetch_notifications = lambda *a, **k: [{"id": 1, "title": "Cũ", "entryDate": "2026-06-01"},
                                             {"id": 2, "title": "Mới", "entryDate": "2026-06-09"}]
    txt = E.notifications_text("t", "FPTU", "HE1")
    assert "Mới" in txt and "Cũ" in txt
    assert txt.index("Mới") < txt.index("Cũ")                         # mới nhất lên đầu
    E.fetch_notifications = lambda *a, **k: []
    assert "Không có thông báo" in E.notifications_text("t", "FPTU", "HE1") or "No notifications" in E.notifications_text("t", "FPTU", "HE1")

def test_notify_seen_corrupt_quarantine():
    """A1: seen_notifications.json HỎNG -> cô lập .corrupt + trả None (coi như first_run), KHÔNG dội cả cửa sổ."""
    import tempfile, io, contextlib, fapc.app.notify as N
    d = tempfile.mkdtemp()
    N._SEEN_NOTIF = os.path.join(d, "seen.json")
    with open(N._SEEN_NOTIF, "w", encoding="utf-8") as f:
        f.write("{ broken json !!!")
    with contextlib.redirect_stdout(io.StringIO()):
        r = N._load_seen()
    assert r is None and os.path.exists(N._SEEN_NOTIF + ".corrupt")   # None -> first_run, file hỏng đã cô lập

def test_gradewatch_component_no_false_ping_on_reformat():
    """A2: đầu điểm '8.5' -> '8.50' (chỉ đổi định dạng) KHÔNG được báo; '8.5' -> '9.0' (đổi thật) phải báo."""
    import fapc.app.gradewatch as G
    m = [{"subjectCode": "X", "courseID": "1", "averageMark": "0.0"}]
    _, st, _ = G.compute(m, lambda s, c: [{"component": "Lab", "value": "8.5"}], {})
    ev, st2, _ = G.compute(m, lambda s, c: [{"component": "Lab", "value": "8.50"}], st)
    assert ev == []                                                  # reformat -> không báo nhầm
    ev2, _, _ = G.compute(m, lambda s, c: [{"component": "Lab", "value": "9.0"}], st2)
    assert any(e["value"] == "9.0" for e in ev2)                     # đổi giá trị thật -> báo

def test_notifications_dedupe():
    import fapc.app.notify as N, fapc.core.extras as E
    from fapc.core import api as A
    orig = (N._load_seen, N._save_seen, N.push)            # KHÔI PHỤC sau test (đừng rò monkeypatch sang test khác)
    try:
        store = {"seen": None}                              # None = file CHƯA tồn tại (chưa ghi mốc)
        N._load_seen = lambda: store["seen"]
        N._save_seen = lambda ids: store.__setitem__("seen", set(ids))
        sent = {}
        N.push = lambda text: (sent.__setitem__("t", text), ["Telegram"])[1]
        A.creds = lambda: ("t", "FPTU", "HE1")
        E.fetch_notifications = lambda *a, **k: [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
        _cap(N.push_new_notifications)                      # lần đầu: baseline, KHÔNG push
        assert "t" not in sent and store["seen"] == {"1", "2"}
        E.fetch_notifications = lambda *a, **k: [{"id": 1, "title": "A"}, {"id": 2, "title": "B"},
                                                 {"id": 3, "title": "C", "entryDate": "2026-06-03"},
                                                 {"title": "không-id"}]   # id rỗng -> KHÔNG bao giờ là 'mới'
        _cap(N.push_new_notifications)                      # chỉ đẩy cái MỚI
        assert "C" in sent.get("t", "") and "A" not in sent["t"] and "không-id" not in sent["t"]
    finally:
        N._load_seen, N._save_seen, N.push = orig

def test_reminders_due_window():
    """Nhắc trước tiết: chỉ tiết bắt đầu trong [now, now+lead] mới 'due'; đã qua / khác ngày / quá xa -> bỏ."""
    from fapc.app.reminders import due_reminders, _key
    now = datetime.datetime(2026, 6, 24, 7, 0)                       # 07:00 ngày 24/06
    soon  = _sess("06/24/2026", "(07:30 - 09:00)", "IAP301", room="BE-304")   # +30'
    later = _sess("06/24/2026", "(09:30 - 11:00)", "CES202")                  # +150'
    past  = _sess("06/24/2026", "(06:00 - 06:50)", "EXE101")                  # -60'
    other = _sess("06/25/2026", "(07:30 - 09:00)", "HOD402")                  # ngày khác
    due = due_reminders([soon, later, past, other], now, 30, set())
    assert len(due) == 1 and due[0][2]["subjectCode"] == "IAP301" and due[0][3] == 30
    # đã nhắc tiết đó -> không nhắc lại (chống spam)
    sent = {due[0][4]}
    assert due_reminders([soon, later, past, other], now, 30, sent) == []
    assert _key(due[0][0], soon) in sent

def test_reminders_text():
    from fapc.app.reminders import reminder_text
    s = _sess("06/24/2026", "(07:30 - 09:00)", "IAP301", room="BE-304")
    start, end = datetime.datetime(2026, 6, 24, 7, 30), datetime.datetime(2026, 6, 24, 9, 0)
    txt = reminder_text(start, end, s, 30)
    assert "IAP301" in txt and "07:30" in txt and "30" in txt and "BE-304" in txt
    assert "ngay" in reminder_text(start, end, s, 0) or "now" in reminder_text(start, end, s, 0)

def test_reminders_lead_config():
    import fapc.config as C, fapc.app.reminders as R
    orig = C.REMIND_MINUTES
    try:
        C.REMIND_MINUTES = "0";   assert R.lead_minutes() == 0 and not R.ClassReminder().enabled()   # tắt
        C.REMIND_MINUTES = "15";  assert R.lead_minutes() == 15
        C.REMIND_MINUTES = "bad"; assert R.lead_minutes() == 0                 # rác -> TẮT (đúng docstring, KHÔNG bật nhầm)
    finally:
        C.REMIND_MINUTES = orig

def test_reminder_tick_strips_tz():
    """Regression: _vn_now() AWARE vs start tiết NAIVE → tick() phải strip tz, KHÔNG raise + vẫn nhắc.
    (Trước fix: 'can't subtract offset-naive and offset-aware datetimes' → nhắc KHÔNG BAO GIỜ chạy.)"""
    import fapc.app.reminders as R, datetime
    sess = _sess("06/27/2026", "(10:00 - 12:15)", "IAP301", room="BE-302", slot="2")
    R.creds = lambda: ("t", "c", "r")
    R.current_semester = lambda *a, **k: "Summer2026"
    R.fetch_sessions = lambda *a, **k: [sess]
    R._vn_now = lambda: datetime.datetime(2026, 6, 27, 9, 40, tzinfo=datetime.timezone.utc)  # AWARE, 20' trước 10:00
    rem = R.ClassReminder(lead=30)
    rem._last_refresh = 9e18                          # bỏ qua _refresh_token (khỏi đụng mạng)
    texts = rem.tick()                                # KHÔNG được raise vì lệch tz
    assert texts and "IAP301" in texts[0]

def test_subjects_resolver():
    """Port #1: danh mục môn -> tên + tín chỉ; thiếu danh mục -> degrade về mã trơ."""
    import fapc.core.subjects as S
    try:
        S.set_index(S.index_of([
            {"subjectCode": "HOD402", "subjectName": "Human-Computer Interaction",
             "subjectV": "Tương tác người-máy", "credits": "3"},
            {"subjectCode": "EXE101", "subjectName": "Experiential Entrepreneurship 1",
             "subjectV": "", "credits": "2"}]))
        assert "HOD402" in S.label("HOD402") and "Tương tác" in S.label("HOD402")   # vi ưu tiên
        assert "Experiential" in S.label("EXE101")                                  # vi rỗng -> fallback en
        assert S.credit_of("HOD402") == 3.0 and S.credit_of("EXE101") == 2.0
        assert S.label("UNKNOWN") == "UNKNOWN" and S.credit_of("UNKNOWN") == 0.0    # ngoài danh mục
        S.set_index({})
        assert S.label("HOD402") == "HOD402" and S.credit_of("HOD402") == 0.0       # không danh mục
    finally:
        S.set_index({})                                                            # dọn để test khác thấy mã trơ

def test_term_gpa_weighted():
    """Port #1: GPA kỳ theo TRỌNG SỐ tín chỉ khi có danh mục; rơi về TB cộng khi không."""
    import fapc.core.grades as G, fapc.core.subjects as S
    rows = [{"subjectCode": "A", "averageMark": "8.0"}, {"subjectCode": "B", "averageMark": "6.0"}]
    try:
        S.set_index({"A": {"credits": 3.0}, "B": {"credits": 1.0}})
        g, w = G.term_gpa(rows)
        assert w is True and g == 7.5                       # (8*3+6*1)/4
        S.set_index({})
        g2, w2 = G.term_gpa(rows)
        assert w2 is False and g2 == 7.0                    # (8+6)/2 — không tín chỉ
    finally:
        S.set_index({})

def test_predict_course():
    """Port #3: cần TB bao nhiêu ở phần còn lại để qua môn (trọng số tự triệt tiêu)."""
    from fapc.core.whatif import predict_course, predict_line
    comps = [{"component": "Assignment", "weight": "30", "value": "8"},
             {"component": "Progress", "weight": "20", "value": "6"},
             {"component": "Final", "weight": "50", "value": ""}]
    p = predict_course(comps, target=5.0)                   # locked=8*30+6*20=360; tot=100; rem=50; need=(500-360)/50=2.8
    assert p["needed"] == 2.8 and p["remaining_pct"] == 50.0 and not p["impossible"] and not p["guaranteed"]
    assert "2.8" in predict_line(p)
    guaranteed = predict_course([{"weight": "80", "value": "9"}, {"weight": "20", "value": ""}])
    assert guaranteed["guaranteed"] is True                 # need=(500-720)/20 < 0 -> chắc qua
    hard = predict_course([{"weight": "60", "value": "0"}, {"weight": "40", "value": ""}])
    assert hard["impossible"] is True                       # need=(500-0)/40 = 12.5 > 10 -> không khả thi
    assert predict_course([{"component": "X", "value": "5"}]) is None   # không trọng số -> None

def test_whatif_final_boundary_display_matches_verdict():
    """Bug audit: môn ĐÃ chốt, raw∈[4.995,5.0) làm tròn lên 5.0 nhưng verdict theo raw thô → '5.0 → NOT passed'.
    Fix: verdict quyết theo `current` (giá trị HIỂN THỊ) nên 5.0 hiển thị -> PASS (khớp nhau)."""
    from fapc.core.whatif import predict_course, predict_line
    p = predict_course([{"weight": "100", "value": "4.997"}], target=5.0)
    assert p["remaining_w"] == 0 and p["current"] == 5.0
    assert p["guaranteed"] is True and p["impossible"] is False        # hiển thị 5.0 -> QUA
    line = predict_line(p, target=5.0)
    assert ("QUA" in line or "PASS" in line) and "5.0" in line
    f = predict_course([{"weight": "100", "value": "4.9"}], target=5.0)  # rõ ràng trượt
    assert f["current"] == 4.9 and f["guaranteed"] is False and f["impossible"] is True

def test_term_gpa_missing_credit_falls_back():
    """Bug audit: 1 môn CÓ điểm nhưng thiếu tín chỉ trong danh mục → KHÔNG âm thầm bỏ rồi vẫn dán nhãn
    'theo tín chỉ'; phải rơi về TB cộng TOÀN BỘ (khớp `fap status`)."""
    import fapc.core.grades as G, fapc.core.subjects as S
    rows = [{"subjectCode": "A", "averageMark": "8.0"}, {"subjectCode": "B", "averageMark": "6.0"}]
    try:
        S.set_index({"A": {"credits": 3.0}})               # B THIẾU tín chỉ
        g, w = G.term_gpa(rows)
        assert w is False and g == 7.0                     # TB cộng (8+6)/2 — KHÔNG phải chỉ mình A=8.0 (weighted)
    finally:
        S.set_index({})

def test_credits_ceil_terms_left():
    """Bug audit: còn tín chỉ mà round() làm tròn xuống '~0 kỳ' (mâu thuẫn). Phải ceil → ≥1 kỳ."""
    import fapc.core.transcript as T
    rows = ([{"subjectCode": f"A{i}", "averageMark": "8", "credit": "16", "semesterName": f"K{i}"} for i in range(8)]
            + [{"subjectCode": "Z", "averageMark": "8", "credit": "15", "semesterName": "K8"}])   # 8*16+15=143, 9 kỳ
    txt = T.credits_text(rows, 145.0)                       # còn 2 tín, avg≈15.9 → ceil(2/15.9)=1 (KHÔNG phải 0)
    assert ("~1 kỳ" in txt) or ("~1 terms" in txt)
    assert ("~0 kỳ" not in txt) and ("~0 terms" not in txt)

def test_weekly_recap_offline():
    """Port #2: `weekly` ghép lịch tuần + điểm danh + điểm trong 1 tin (KHÁC alias 'week' cũ)."""
    import fapc.app.bot_core as B, fapc.core.grades as G, fapc.core.subjects as S
    marks = lambda *a, **k: [{"subjectCode": "EXE101", "averageMark": "8.0", "status": "Passed", "courseID": None}]
    B.creds = lambda: ("tok", "FPTU", "HE190000")
    B.current_semester = lambda *a, **k: "Summer2026"
    B.fetch_sessions = lambda *a, **k: [MON, MON2, WED]
    B.fetch_marks = marks; G.fetch_marks = marks
    B.fetch_att = lambda *a, **k: [{"subjectCode": "EXE101", "attendance": "100"}]
    B._vn_now = lambda: datetime.datetime(2026, 6, 15, 8, 0)
    S.set_index({})
    out = B.handle("weekly")
    assert "EXE101" in out and ("Tuần" in out or "Week" in out) and ("Điểm danh" in out or "Attendance" in out)

def test_courses_resolver_and_roster():
    """Port #7/#8: course_id_map (vá courseID), roster, fallback từ TKB — chấp nhận đa biến thể field."""
    import fapc.core.courses as C
    rows = [{"subjectCode": "IAP301", "courseId": "2", "className": "IA1900", "teacherCode": "AnhHT68", "roomNo": "BE-213"},
            {"SubjectCode": "FRS401c", "courseID": "9"},          # khác hoa/thường vẫn nhận
            {"subjectCode": "", "courseId": "x"}]                 # thiếu mã -> bỏ
    cmap = C.course_id_map(rows)
    assert cmap == {"IAP301": "2", "FRS401c": "9"}               # vá được cả 2, bỏ dòng rỗng
    r = C.roster(rows)
    assert r[0]["lecturer"] == "AnhHT68" and r[0]["room"] == "BE-213" and len(r) == 2
    # fallback gộp buổi TKB theo môn, union phòng
    sess = [{"subjectCode": "IAP301", "roomNo": "BE-213", "groupName": "G"},
            {"subjectCode": "IAP301", "roomNo": "BE-304", "groupName": "G"}]
    fb = C.roster_from_activity(sess)
    assert len(fb) == 1 and "BE-213" in fb[0]["room"] and "BE-304" in fb[0]["room"]

def test_grades_detail_merges_missing_subject():
    """Port #7: môn GetStudentMark BỎ SÓT (chỉ có trong GetCourseOfSemester) vẫn hiện điểm thành phần."""
    import fapc.core.grades as G, fapc.core.courses as C
    G.fetch_marks = lambda *a, **k: [{"subjectCode": "IAP301", "courseID": "2"}]   # chỉ 1 môn có điểm
    C.fetch_courses = lambda *a, **k: [{"subjectCode": "IAP301", "courseId": "2"},
                                       {"subjectCode": "FRS401c", "courseId": "9"}]  # FRS401c bị GetStudentMark bỏ sót
    G.call = lambda *a, **k: (200, {"data": [{"courseID": 9, "item": "Lab", "value": "7.0", "weight": "100"}]})
    txt = G.detail_text("t", "FPTU", "HE1", "Summer2026")
    assert "IAP301" in txt and "FRS401c" in txt                  # cả môn bù cũng hiện
    assert "2 môn" in txt or "2 subjects" in txt

def test_gpa_trend():
    """gpa-trend: sắp xếp kỳ theo thời gian + delta + sparkline (GPA theo tín chỉ)."""
    import fapc.core.transcript as T
    assert T._sem_key("Spring2025") < T._sem_key("Summer2025") < T._sem_key("Fall2025") < T._sem_key("Spring2026")
    assert T._sem_key("???") == (9999, 9, "???")             # không parse được -> đẩy cuối
    sp = T._sparkline([6.0, 7.0, 8.0])
    assert len(sp) == 3 and sp[0] == "▁" and sp[-1] == "█"
    assert T._sparkline([7.0]) == ""                         # < 2 điểm -> rỗng
    rows = [{"semesterName": "Fall2025", "averageMark": "8", "credit": "3"},
            {"semesterName": "Spring2025", "averageMark": "6", "credit": "3"}]
    txt = T.trend_text(rows)
    assert txt.index("Spring2025") < txt.index("Fall2025")   # kỳ cũ hiện trước (đã sắp thời gian)
    assert "▲2.00" in txt                                    # Fall lên 2.00 so kỳ trước
    assert T.trend_text([]).strip().startswith("📈")         # rỗng -> thông báo, KHÔNG lỗi

def test_conduct_graceful():
    """conduct: code 201 + NullReference (data null) -> coi như CHƯA có điểm, KHÔNG raise như token hết hạn."""
    import fapc.core.conduct as K
    K.call = lambda *a, **k: (200, {"code": "201", "message": "Thành công", "data": None})
    assert K.fetch("t", "c", "r", "Summer2026") == []        # null/NullReference -> [] (không raise)
    assert "rèn luyện" in K.conduct_text("t", "c", "r", "Summer2026")
    K.call = lambda *a, **k: (200, {"code": "201", "message": "Token invalid", "data": None})
    raised = False
    try: K.fetch("t", "c", "r", "Summer2026")                # token THẬT hết hạn -> phải raise
    except SystemExit: raised = True
    assert raised

def test_exam_countdown():
    """exam-countdown: bỏ thi đã qua, sắp xếp sớm nhất trước, nhãn độ gấp ('now' truyền vào)."""
    import fapc.core.extras as E, fapc.core.subjects as S
    now = datetime.datetime(2026, 6, 24, 8, 0)
    rows = [{"subjectCode": "IAP301", "examDate": "06/26/2026", "examTime": "07:30", "examRoom": "BE-101"},
            {"subjectCode": "CES202", "examDate": "06/20/2026", "examTime": "07:30"},   # đã qua → bỏ
            {"subjectCode": "HOD402", "examDate": "06/24/2026", "examTime": "13:30"}]   # hôm nay
    items = E.exam_countdown(rows, now)
    assert [i[2] for i in items] == ["HOD402", "IAP301"]      # quá khứ bị bỏ; sớm nhất trước
    assert items[0][0] == 0 and items[1][0] == 2             # days: hôm nay=0, +2
    S.set_index({}); E._exam_rows = lambda *a, **k: rows
    assert "HÔM NAY" in E.countdown_text("t", "c", "r", "S", now=now) or "TODAY" in E.countdown_text("t","c","r","S",now=now)
    E._exam_rows = lambda *a, **k: []
    assert E.countdown_text("t", "c", "r", "S", now=now).strip().startswith("⏳")   # rỗng → thông báo

def test_credits_progress():
    """credits: đếm tín chỉ môn ĐÃ qua (mark>0 & credit>0) + % + thanh tiến độ."""
    from fapc.core.transcript import credits_text
    rows = [{"semesterName": "Fall2024", "averageMark": "8", "credit": "3"},
            {"semesterName": "Fall2024", "averageMark": "7", "credit": "3"},
            {"semesterName": "Spring2025", "averageMark": "0", "credit": "3"},   # chưa có điểm → không tính
            {"semesterName": "Spring2025", "averageMark": "9", "credit": "2"}]
    txt = credits_text(rows, total=100)
    assert "8/100" in txt and "8.0%" in txt and "█" in txt    # 3+3+2 = 8 tín chỉ đạt + thanh
    assert credits_text([], 100).strip().startswith("🎓")     # rỗng → thông báo, không lỗi

def test_whoami_offline_jwt():
    """whoami --offline: decode JWT (KHÔNG xác minh chữ ký) + token_freshness theo claim exp."""
    import base64, json as _json
    from fapc.core.auth import decode_jwt, token_freshness
    mk = lambda p: "h." + base64.urlsafe_b64encode(_json.dumps(p).encode()).decode().rstrip("=") + ".sig"
    c = decode_jwt(mk({"username": "he190000", "email": "x@fpt.edu.vn", "exp": 2000}))
    assert c["username"] == "he190000" and c["email"] == "x@fpt.edu.vn"
    assert decode_jwt("not-a-jwt") == {} and decode_jwt("") == {}     # méo → {} (không raise)
    assert token_freshness({"exp": 2000}, now=1000) == ("valid", 1000)
    assert token_freshness({"exp": 1000}, now=2000) == ("expired", 1000)
    assert token_freshness({}) == ("unknown", 0)

def _login_sandbox():
    """Trỏ auth.TOKEN_JSON/PKCE_STATE vào thư mục tạm — test đăng nhập TUYỆT ĐỐI không đụng token thật."""
    import tempfile, os as _os, fapc.core.auth as A
    d = tempfile.mkdtemp()
    saved = (A.TOKEN_JSON, A.PKCE_STATE, A.OAUTH_JSON,
             A.device_start, A.device_poll, A._finalize, A.exchange_code)
    A.TOKEN_JSON = _os.path.join(d, "token.json")
    A.OAUTH_JSON = _os.path.join(d, "oauth.json")
    A.PKCE_STATE = _os.path.join(d, "pkce.json")
    # CẤM MẠNG: bộ test này là OFFLINE. Chặn sẵn cả 2 cửa ra để một nhánh quên stub sẽ NỔ ngay
    # thay vì lặng lẽ bắn request thật tới feid.fpt.edu.vn (bot chạy `selftest` mỗi lần /update!).
    A.device_start = lambda: (False, "offline-test")
    A.device_poll = lambda *a, **k: (_ for _ in ()).throw(AssertionError("test gọi mạng!"))
    A.exchange_code = lambda *a, **k: (_ for _ in ()).throw(AssertionError("test gọi mạng!"))
    return A, saved

def _login_restore(A, saved):
    (A.TOKEN_JSON, A.PKCE_STATE, A.OAUTH_JSON,
     A.device_start, A.device_poll, A._finalize, A.exchange_code) = saved

def test_login_start_device_keeps_code_out_of_chat():
    """Đăng nhập từ chat: đường DEVICE chỉ gửi LINK — mã uỷ quyền không bao giờ nằm trong tin nhắn."""
    import fapc.app.botlogin as BL
    A, saved = _login_sandbox()
    try:
        A.device_start = lambda: (True, {"device_code": "DC", "user_code": "ABCD-1234", "interval": 1,
                                         "expires_in": 60,
                                         "verification_uri_complete": "https://feid.fpt.edu.vn/device?u=ABCD-1234"})
        ok, text, mode = BL.LoginSession().start("APHL")
        assert ok and mode == "device"
        assert "code=" not in text and "access_token" not in text   # không rò mã/token vào chat
        assert "ABCD-1234" in text                                  # nhưng vẫn đưa mã xác nhận cho người dùng
    finally:
        _login_restore(A, saved)

def test_login_refuses_different_account():
    """CHỐT CHẶN: đăng nhập ra roll KHÁC -> từ chối + HOÀN TÁC **CẢ HAI** file token.

    Stub phải GHI FILE y như đường thật (_finalize ghi oauth_tokens.json TRƯỚC, _do_fap ghi token.json
    sau). Nếu stub chỉ trả dict thì test vẫn xanh dù đã xoá sạch phần hoàn tác — vô nghĩa.
    Hoàn tác oauth_tokens.json là BẮT BUỘC: refresh_token của người lạ còn ở đó thì lần refresh sau
    sẽ dựng lại token của họ, và refresh_tokens() không hề kiểm tra tài khoản."""
    import json as _json
    A, saved = _login_sandbox()
    try:
        with open(A.TOKEN_JSON, "w", encoding="utf-8") as f:
            _json.dump({"rollnumber": "HE191048", "campus": "APHL"}, f)
        with open(A.OAUTH_JSON, "w", encoding="utf-8") as f:
            _json.dump({"refresh_token": "MINE"}, f)

        def _fin_foreign(tok, campus, log=print):
            A._save(A.OAUTH_JSON, {"refresh_token": "THEIRS"})      # y như _finalize thật
            A._save(A.TOKEN_JSON, {"rollnumber": "HE999999", "campus": "APHL"})
            return {"rollnumber": "HE999999", "campus": "APHL"}
        A.device_poll = lambda *a, **k: {"access_token": "x"}
        A._finalize = _fin_foreign
        ok, msg = A.login_finish_device({"device_code": "DC", "campus": "APHL"}, A.current_roll())
        assert ok is False and "HE999999" in msg and "HE191048" in msg
        with open(A.TOKEN_JSON, encoding="utf-8") as f:
            assert _json.load(f)["rollnumber"] == "HE191048"        # token CŨ còn nguyên
        with open(A.OAUTH_JSON, encoding="utf-8") as f:
            assert _json.load(f)["refresh_token"] == "MINE"         # refresh_token lạ ĐÃ bị gỡ

        # roll RỖNG (FAP trả data dạng chuỗi trần) cũng phải bị coi là KHÁC — không định danh được thì cấm
        A._finalize = lambda tok, campus, log=print: {"rollnumber": None, "campus": "APHL"}
        assert A.login_finish_device({"device_code": "DC", "campus": "APHL"}, "HE191048")[0] is False

        A._finalize = lambda tok, campus, log=print: {"rollnumber": "HE191048", "campus": "APHL"}
        ok2, msg2 = A.login_finish_device({"device_code": "DC", "campus": "APHL"}, A.current_roll())
        assert ok2 is True and "HE191048" in msg2                   # đúng tài khoản -> cho qua
    finally:
        _login_restore(A, saved)

def test_login_pkce_paste_detection_and_ttl():
    """Đường PKCE (dự phòng): nhận diện URL redirect để XOÁ tin ngay, và hết hạn chờ thì từ chối."""
    import fapc.app.botlogin as BL
    A, saved = _login_sandbox()
    try:
        # Nhận diện phải RỘNG TAY: thà xoá nhầm tin vô hại còn hơn để lọt mã uỷ quyền vào lịch sử chat.
        assert A.looks_like_redirect("io.identityserver.demo:/oauthredirect?code=Z9&state=q") is True
        assert A.looks_like_redirect("https://x/cb?error=access_denied") is True   # nhánh LỖI cũng phải nhận
        assert A.looks_like_redirect("/today") is False
        assert A.looks_like_redirect("") is False
        s = BL.LoginSession()                                       # device_start đã bị ép fail -> PKCE
        ok, text, mode = s.start("APHL")
        assert ok and mode == "pkce" and s.waiting_paste()
        assert not s.waiting_paste(now=s.started + BL.PASTE_TTL + 1)  # quá hạn -> không nhận dán nữa
        A.exchange_code = lambda pasted, log=print: {"rollnumber": "HE191048", "campus": "APHL"}
        ok2, msg2 = BL.finish_paste(s, "io.identityserver.demo:/oauthredirect?code=Z9")
        assert ok2 is True and "HE191048" in msg2                   # dán hợp lệ -> đổi được token
        assert BL.finish_paste(s, "x")[0] is False                  # phiên đã đóng -> từ chối, không nổ
    finally:
        _login_restore(A, saved)

def test_login_missing_campus_and_busy():
    """Thiếu campus -> hướng dẫn rõ; đang có phiên chạy dở -> không mở phiên thứ hai (tránh đè .pkce_state)."""
    import fapc.app.botlogin as BL
    A, saved = _login_sandbox()
    try:
        ok, text, mode = BL.LoginSession().start("")
        assert ok is False and mode is None and ("campus" in text.lower())
        A.device_start = lambda: (True, {"device_code": "DC", "interval": 1, "expires_in": 60,
                                         "verification_uri_complete": "https://x/y"})
        s = BL.LoginSession()
        assert s.start("APHL")[0] is True and s.busy is True        # device: giữ cờ bận khi đang chờ duyệt
        ok2, text2, _ = s.start("APHL")
        assert ok2 is False and ("dở" in text2 or "progress" in text2.lower())
    finally:
        _login_restore(A, saved)

def test_news_search():
    """news <từ khoá> → SearchNews(keysearch); không từ khoá → GetTop10News. Decode entity."""
    import fapc.core.extras as E
    seen = {}
    def fake(ep, params, *a, **k):
        seen["ep"] = ep; seen["p"] = dict(params)
        return (200, {"data": [{"title": "Học bổng &amp; quà"}]})
    E.call = fake
    rows = E.fetch_news("t", "c", "r", keyword="học bổng", type="1")
    assert seen["ep"] == "SearchNews" and seen["p"].get("keysearch") == "học bổng" and seen["p"].get("type") == "1"
    assert rows[0]["title"] == "Học bổng & quà"              # &amp; → &
    E.fetch_news("t", "c", "r")                              # không keyword → top-10
    assert seen["ep"] == "GetTop10News"

def test_news_text_render_offline():
    """news_text render SẠCH: bóc thẻ HTML, tiêu đề + ngày + trích, MỚI NHẤT trước. Field FAP: 'tittle'/'content'/'createDate'."""
    import fapc.core.extras as E
    orig = E.fetch_news                                       # KHÔI PHỤC sau test (đừng rò sang smoke ex.news)
    try:
        E.fetch_news = lambda *a, **k: [
            {"tittle": "Tin cũ", "content": "<p>abc</p>", "createDate": "2026-07-01T08:00:00"},
            {"tittle": "Tin mới &amp; nóng", "content": "<p>xin <b>chào</b> &nbsp; thế giới</p>",
             "createDate": "2026-07-31T10:00:00"}]
        out = E.news_text("t", "c", "r")
        assert out.index("Tin mới") < out.index("Tin cũ")    # mới nhất trước (sort theo createDate desc)
        assert "&" in out and "&amp;" not in out             # entity đã decode
        assert "<p>" not in out and "<b>" not in out         # thẻ HTML đã bóc
        assert "xin chào thế giới" in out                    # gộp khoảng trắng (kể cả &nbsp;), giữ text
        assert "31/07/2026" in out                           # ngày đã format
        E.fetch_news = lambda *a, **k: []
        assert "Không có tin" in E.news_text("t", "c", "r") or "No news" in E.news_text("t", "c", "r")
    finally:
        E.fetch_news = orig

def test_calendar_prune_plan():
    """calendar-prune: CHỈ đánh dấu xóa event fapc KHÔNG còn trong lịch hiện tại (giữ event còn, bỏ event thiếu uid)."""
    import fapc.app.gcal as G
    fapc_events = [
        {"id": "e1", "iCalUID": "fapc-20260627-IAP301-2@fap.fpt.edu.vn", "summary": "IAP301"},   # còn → giữ
        {"id": "e2", "iCalUID": "fapc-20260601-OLD101-1@fap.fpt.edu.vn", "summary": "OLD101"},    # mồ côi → xóa
        {"id": "e3", "iCalUID": "", "summary": "no-uid"},                                          # thiếu uid → bỏ qua
    ]
    plan = G._prune_plan(fapc_events, {"fapc-20260627-IAP301-2@fap.fpt.edu.vn"})
    assert [p[2] for p in plan] == ["OLD101"] and [p[0] for p in plan] == ["e2"]

def test_exams_text_format_offline():
    """Feature 2: exams_text định dạng SẠCH (không đổ thô r.values()) — tên môn + DD/MM/YYYY HH:MM +
    phòng + loại thi, SẮP XẾP sớm nhất trước; ngày US 'm/d/Y' được ĐỔI sang DD/MM/YYYY."""
    import fapc.core.extras as E, fapc.core.subjects as S
    S.set_index(S.index_of([{"subjectCode": "IAP301", "subjectName": "Interaction Design",
                             "subjectV": "", "credits": "3"}]))
    try:
        rows = [{"subjectCode": "HOD402", "examDate": "06/26/2026", "examTime": "13:30", "examRoom": "BE-205", "examType": "FE"},
                {"subjectCode": "IAP301", "examDate": "06/25/2026", "examTime": "07:30", "examRoom": "BE-101", "examType": "PE"}]
        E.call = lambda *a, **k: (200, {"code": "200", "data": rows})
        txt = E.exams_text("t", "FPTU", "HE1", "Summer2026")
        assert "25/06/2026 07:30" in txt and "BE-101" in txt          # ngày ĐÃ đổi định dạng + giờ + phòng
        assert "Interaction Design" in txt                            # join tên môn từ danh mục
        assert "FE" in txt and "PE" in txt                            # loại kỳ thi (examType) hiện ra
        assert txt.index("IAP301") < txt.index("HOD402")             # 25/06 trước 26/06 (sắp thời gian)
        assert "06/25/2026" not in txt                               # KHÔNG còn ngày US thô -> đã format
    finally:
        S.set_index({})

def test_exams_text_multivariant_fields():
    """Feature 2: nhận tên field KHÁC hoa/thường & biến-thể (SubjectCode/date/time/room) mà vẫn format đúng."""
    import fapc.core.extras as E, fapc.core.subjects as S
    S.set_index({})
    rows = [{"SubjectCode": "CES202", "date": "07/01/2026", "time": "09:15", "room": "AL-R201"}]
    E.call = lambda *a, **k: (200, {"code": "200", "data": rows})
    txt = E.exams_text("t", "FPTU", "HE1", "Summer2026")
    assert "CES202" in txt and "01/07/2026 09:15" in txt and "AL-R201" in txt

def test_selfupdate_perform_update_decisions():
    """Feature 1: perform_update quyết định restart ĐÚNG theo trạng thái pull + kết quả selftest."""
    import fapc.app.selfupdate as U
    orig = (U.pull, U.run_selftest)
    try:
        U.run_selftest = lambda: (True, "ok")
        for st in ("uptodate", "notgit", "dirty", "pullerror"):
            U.pull = lambda st=st: {"status": st, "message": "x"}
            assert U.perform_update()[1] is False, st                 # các trạng thái này KHÔNG restart
        U.pull = lambda: {"status": "updated", "message": "a→b", "deps_changed": False}
        assert U.perform_update()[1] is True                          # updated + selftest PASS -> restart
        U.run_selftest = lambda: (False, "boom FAILED")
        s, r = U.perform_update(); assert r is False and "FAIL" in s   # selftest FAIL -> KHÔNG restart
        U.run_selftest = lambda: (True, "ok")
        U.pull = lambda: {"status": "updated", "message": "a→b", "deps_changed": True}
        assert U.perform_update()[1] is False                         # deps đổi -> KHÔNG tự restart
    finally:
        U.pull, U.run_selftest = orig

def test_selfupdate_autoupdate_min_and_noop():
    """Feature 1: autoupdate_min đọc FAP_AUTOUPDATE_MIN; maybe_autoupdate khi TẮT (0) là no-op (không pull)."""
    import fapc.app.selfupdate as U, fapc.config as C
    orig_cfg, orig_pull = C.AUTOUPDATE_MIN, U.pull
    called = {"pull": False}
    try:
        U.pull = lambda: (called.__setitem__("pull", True), {"status": "uptodate", "message": ""})[1]
        C.AUTOUPDATE_MIN = "0"
        assert U.autoupdate_min() == 0
        assert U.maybe_autoupdate(0.0, 10_000.0, log=lambda m: None) == 0.0 and called["pull"] is False
        C.AUTOUPDATE_MIN = "45";  assert U.autoupdate_min() == 45
        C.AUTOUPDATE_MIN = "bad"; assert U.autoupdate_min() == 0       # rác -> 0 (tắt)
    finally:
        C.AUTOUPDATE_MIN, U.pull = orig_cfg, orig_pull

def test_markbycourse_html_parse():
    """GetMarkByCourse trả BẢNG HTML → _normalize_components parse ra {category,item,weight,value}, bỏ 'Total'+header."""
    import fapc.core.grades as G
    html = ("<table><tr><th>Grade category</th><th>Grade item</th><th>Weight</th><th>Value</th><th>Comment</th></tr>"
            "<tr><td rowspan='2'>Progress test 1</td><td>Progress test 1</td><td>10.0 %</td><td>9.7</td><td></td></tr>"
            "<tr><td>Total</td><td>10.0 %</td><td></td><td></td></tr>"
            "<tr><td rowspan='2'>LAB</td><td>LAB 1</td><td>1.7 %</td><td>9</td><td></td></tr>"
            "<tr><td>LAB 2</td><td>1.7 %</td><td></td><td></td></tr>"
            "<tfoot><tr><td rowspan='2'>Course total</td><td>Average</td><td colspan='3'>0.0</td></tr>"
            "<tr><td>Status</td><td colspan='3'>Not Passed</td></tr></tfoot></table>")
    comps = G._normalize_components({"data": html})           # như fetch_components (unwrap -> chuỗi HTML)
    got = {(c["item"], c["value"]) for c in comps}
    assert ("Progress test 1", "9.7") in got and ("LAB 1", "9") in got
    assert all(c["item"] != "Total" for c in comps)           # bỏ subtotal + không có header 'Grade item'
    lab1 = next(c for c in comps if c["item"] == "LAB 1")
    assert lab1["category"] == "LAB" and lab1["weight"] == "1.7 %"   # rowspan category gán đúng

def test_exam_dt_time_field_h():
    """M9 fix: giờ thi lấy từ field 'time'='14h30-16h00' (dấu h), KHÔNG lấy '00:00' từ date '...T00:00:00'."""
    from fapc.core.extras import _exam_dt
    s, _ = _exam_dt({"subjectCode": "IAP301", "date": "2026-07-27T00:00:00", "time": "14h30-16h00"})
    assert (s.hour, s.minute) == (14, 30)                     # giờ ĐẦU của khoảng, không phải 00:00
    s2, _ = _exam_dt({"date": "2026-07-27T00:00:00"})         # thiếu time → mặc định 07:00 (bỏ 00:00 giả)
    assert (s2.hour, s2.minute) == (7, 0)
    s3, _ = _exam_dt({"date": "2026-06-05T13:30:00"})         # date có giờ THẬT nhúng → dùng luôn
    assert (s3.hour, s3.minute) == (13, 30)

def test_predict_course_skips_resit_total():
    """predict_course bỏ dòng 'Total' (subtotal) + 'Resit' (thi lại) → không cộng dồn trọng số."""
    from fapc.core.whatif import predict_course
    comps = [{"item": "Progress test 1", "weight": "10.0 %", "value": "8"},
             {"item": "Total", "weight": "10.0 %", "value": ""},              # bỏ
             {"item": "Final exam", "weight": "30.0 %", "value": ""},
             {"item": "Final exam Resit", "weight": "30.0 %", "value": ""}]   # bỏ (thi lại)
    p = predict_course(comps, target=5.0)
    assert p["total_w"] == 40.0                               # 10 + 30 (bỏ Total 10 + Resit 30)

# ---- roadmap §18: gộp thông báo · cắt tin dài · profile · máy chỉ-đọc ----
# Mọi assert dưới đây tránh phụ thuộc NGÔN NGỮ: chỉ bám phần chung của cặp t(vi, en)
# ('· 5' có trong cả '· 5 điểm mới' lẫn '· 5 new marks') -> không vỡ khi FAP_LANG đổi.

def test_gradewatch_render_events_collapses_long_run():
    """Ca 'baseline lại' (47 điểm một lúc) làm tin nhắn dài 54 dòng. Run cùng tiền tố ≥4 mục phải gộp
    thành 'chủ đạo + ngoại lệ'; header môn BẮT BUỘC mang SỐ điểm mới, nếu không 'LAB 1–5' bị đọc nhầm
    là TOÀN BỘ lab của môn trong khi event chỉ chứa lab VỪA ĐỔI.
    A run of >=4 same-prefix items collapses to mode + exceptions; the subject header MUST carry the
    count, otherwise 'LAB 1-5' reads as *all* labs instead of only the ones that just changed."""
    from fapc.app.gradewatch import render_events, _RUN_MIN, _mode
    assert _RUN_MIN == 4                                      # ngưỡng gộp (dưới ngưỡng -> in bình thường)
    ev = [{"subj": "HOD402", "item": f"LAB {i}", "value": "7" if i == 3 else "9"} for i in range(1, 6)]
    out = render_events(ev)
    assert "HOD402 · 5" in out                                # số điểm mới ở header môn
    assert "LAB 1–5" in out                                   # số LIÊN TIẾP -> ghi dải
    assert "LAB 3: 7" in out                                  # ngoại lệ vẫn hiện đủ giá trị
    assert "LAB 1: 9" not in out and "LAB 5: 9" not in out    # mục theo chủ đạo KHÔNG lặp lại
    assert len(out.splitlines()) == 2                         # header + ĐÚNG 1 dòng nhóm 🔬
    gappy = render_events([{"subj": "X", "item": f"LAB {i}", "value": "9"} for i in (1, 3, 5, 9)])
    assert "LAB 1–9" not in gappy and "LAB 1,3,5,9" in gappy  # đứt quãng -> KHÔNG nói dối phạm vi
    assert _mode(["9", "8", "7", "6"]) is None                # mỗi mục một giá trị -> không có chủ đạo

def test_gradewatch_render_events_short_case_stays_short():
    """Bình thường chỉ 1–3 điểm/lần: cách gộp mới KHÔNG được làm ca ít điểm dài ra.
    The common 1-3 mark case must stay exactly as short as before — a 2-item run must NOT collapse."""
    from fapc.app.gradewatch import render_events
    two = render_events([{"subj": "X", "item": "LAB 1", "value": "8"},
                         {"subj": "X", "item": "LAB 2", "value": "9"}])
    assert "LAB 1–2" not in two                               # dưới ngưỡng -> KHÔNG gộp
    assert "LAB 1: 8" in two and "LAB 2: 9" in two            # liệt kê đủ, nối ' · ' trên 1 dòng
    assert len(two.splitlines()) == 2                         # header + 1 dòng
    three = render_events([{"subj": "X", "item": "LAB 12", "value": "8"},
                           {"subj": "X", "item": "Final exam", "value": "7.6"},
                           {"subj": "X", "item": None, "value": "8.5"}])   # item=None = điểm tổng kết
    assert "X · 3" in three                                   # đếm CẢ điểm tổng kết
    assert len(three.splitlines()) == 4                       # header + 🔬 + 🏁 + ★
    assert three.splitlines()[-1].lstrip().startswith("★")    # điểm tổng kết ở CUỐI khối môn
    assert render_events([]) == ""

def test_fmt_chunks_no_data_loss():
    """fmt.chunks thay cho text[:4000]/[:1900] — cắt cụt LÀ MẤT DỮ LIỆU thật (/grades-detail 6 môn mất
    3425 ký tự trên Discord). Mọi mẩu ≤ limit, ưu tiên ranh giới dòng, nối lại KHÔNG mất chữ.
    Chunking replaces hard truncation, which really did drop text; nothing may be lost."""
    from fapc.fmt import chunks
    assert chunks("ngắn", 100) == ["ngắn"]                    # dưới hạn -> nguyên văn, 1 mẩu
    assert chunks("abc", 0) == ["abc"] and chunks("abc", -1) == ["abc"] and chunks("abc", None) == ["abc"]
    assert chunks("", 10) == [""]                             # LUÔN trả ≥1 phần tử
    text = "\n".join(f"📘 dòng {i} " + "x" * 20 for i in range(60))
    parts = chunks(text, 200)
    assert len(parts) > 1                                     # dài hơn hạn -> nhiều mẩu
    assert max(len(p) for p in parts) <= 200                  # không mẩu nào vượt hạn
    assert "\n".join(parts) == text                           # cắt ở RANH GIỚI DÒNG -> ghép lại y nguyên
    long_line = "y" * 450                                     # 1 dòng dài quá khổ -> buộc cắt CỨNG
    hard = chunks(long_line, 100)
    assert len(hard) == 5 and max(len(p) for p in hard) <= 100
    assert "".join(hard) == long_line                         # cắt cứng cũng KHÔNG mất ký tự nào

def test_paths_profile_resolution():
    """FAP_PROFILE chưa đặt ⇒ đường dẫn ra ĐÚNG chuỗi cũ <root>/output/<file> — đây là CAM KẾT tương
    thích ngược (máy đang chạy không phải migrate). Có profile ⇒ output/profiles/<tên>/. Tên độc hại
    (thoát thư mục) rơi về mặc định, KHÔNG raise: một biến gõ nhầm không được làm chết mọi lệnh.
    No profile MUST resolve to the exact legacy path; hostile names fall back instead of escaping."""
    from fapc.core import paths
    saved = os.environ.get("FAP_PROFILE")
    try:
        os.environ.pop("FAP_PROFILE", None)
        assert paths.profile() == "" and paths.label() == ""
        assert paths.out_dir() == os.path.join(paths.ROOT, "output")
        assert paths.out("token.json") == os.path.join(paths.ROOT, "output", "token.json")
        assert paths.out("api", "x.json") == os.path.join(paths.ROOT, "output", "api", "x.json")
        os.environ["FAP_PROFILE"] = "alice"
        assert paths.profile() == "alice" and paths.label() == " [alice]"
        assert paths.out("token.json") == os.path.join(paths.ROOT, "output", "profiles", "alice", "token.json")
        for bad in ("../../etc", "", "   ", "a/b", "a\\b", ".", "..", "~", "al ice"):
            os.environ["FAP_PROFILE"] = bad
            assert paths.profile() == "", bad                 # tên sai -> coi như KHÔNG có profile
            assert paths.out_dir() == os.path.join(paths.ROOT, "output"), bad   # không thoát ra ngoài output/
    finally:
        if saved is None: os.environ.pop("FAP_PROFILE", None)
        else: os.environ["FAP_PROFILE"] = saved

def test_auth_token_readonly_refuses_refresh():
    """FE Identity XOAY VÒNG refresh_token: máy nào refresh trước thì bản của máy kia thành vô hiệu.
    FAP_TOKEN_READONLY=1 phải CHẶN refresh NGAY (trước mọi đọc file/gọi mạng) và hét TO ra log.
    Chạy hoàn toàn offline: chỉ vá config, không đụng mạng lẫn oauth_tokens.json."""
    import fapc.config as C, fapc.core.auth as A
    assert A._truthy("1") and A._truthy(" TRUE ") and A._truthy("on") and A._truthy("Yes")
    assert not A._truthy("0") and not A._truthy("") and not A._truthy(None) and not A._truthy("false")
    old = C.TOKEN_READONLY
    try:
        C.TOKEN_READONLY = "0"                                # '0' trong .env = TẮT (bool('0') là True -> bẫy)
        assert A.token_readonly() is False
        C.TOKEN_READONLY = "1"
        assert A.token_readonly() is True
        out, err, refused = io.StringIO(), io.StringIO(), False
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                A.refresh_tokens()
            except SystemExit:
                refused = True
        assert refused                                        # TỪ CHỐI, không refresh
        loud = err.getvalue() + out.getvalue()
        assert "FAP_TOKEN_READONLY" in loud and "!!!!" in loud # banner phải nhìn thấy được trong log
    finally:
        C.TOKEN_READONLY = old

def test_env_loader_profile_does_not_inherit_identity_keys():
    """Lỗi RÒ DỮ LIỆU: profile của bạn bè thừa kế TELEGRAM_CHAT của chủ máy ⇒ điểm của bạn bè bắn vào
    chat chủ máy. Khóa mang DANH TÍNH không được thừa kế (thiếu ⇒ kênh TẮT HẲN — an toàn); khóa mức
    MÁY vẫn thừa kế bình thường. Dùng .env GIẢ trong thư mục tạm — KHÔNG bao giờ đọc .env thật.
    A profile must never inherit the owner's delivery identity; non-identity keys still inherit."""
    import tempfile, fapc
    keys = ("FAP_PROFILE", "TELEGRAM_CHAT", "TELEGRAM_TOKEN", "ZZ_FAKE_SHARED_KEY")
    saved = {k: os.environ.get(k) for k in keys}
    old_file, old_loaded = fapc.__file__, fapc._ENV_LOADED
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as f:          # .env của CHỦ MÁY
            f.write("TELEGRAM_CHAT=OWNER_CHAT\nTELEGRAM_TOKEN=OWNER_TOKEN\nZZ_FAKE_SHARED_KEY=shared\n")
        with open(os.path.join(tmp, ".env.alice"), "w", encoding="utf-8") as f:    # alice KHÔNG khai CHAT
            f.write("TELEGRAM_TOKEN=ALICE_TOKEN\n")
        for k in keys:
            os.environ.pop(k, None)
        os.environ["FAP_PROFILE"] = "alice"
        fapc.__file__ = os.path.join(tmp, "fapc", "__init__.py")   # -> gốc repo giả = tmp
        fapc._ENV_LOADED = False                                   # loader idempotent -> mở khoá để nạp lại
        fapc.load_env()
        assert os.environ.get("TELEGRAM_CHAT") is None       # KHÔNG thừa kế -> không rò vào chat chủ máy
        assert os.environ.get("TELEGRAM_TOKEN") == "ALICE_TOKEN"   # .env.<profile> THẮNG .env gốc
        assert os.environ.get("ZZ_FAKE_SHARED_KEY") == "shared"    # khóa mức máy vẫn thừa kế
        assert "TELEGRAM_CHAT" in fapc._IDENTITY_KEYS and "GCAL_CALENDAR_ID" in fapc._IDENTITY_KEYS
    finally:
        fapc.__file__, fapc._ENV_LOADED = old_file, old_loaded
        for k, v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

def test_gcal_owner_scoped_uid_and_ownership():
    """Blocker §4: nhiều profile dùng CHUNG một lịch Google thì prune của profile này XÓA sự kiện của
    profile kia. Sự kiện nay gắn nhãn fapc_owner=<mã SV>: _is_mine chỉ nhận sự kiện của CHÍNH mình,
    lịch CŨ (chưa có nhãn) chỉ thuộc profile mặc định; uid cũ đã có trên lịch thì TÁI DÙNG (cập nhật
    tại chỗ, không nhân đôi, không xóa gì).
    Ownership is keyed by student roll, so one profile can never claim - let alone prune - another's."""
    from fapc.app.gcal import _owner, _uids_for, _pick_uid, _is_mine, _current_uids
    assert _owner("HE170001") == "he170001" and _owner("he-17/0001") == "he170001"
    assert _owner(None) == "unknown"                          # không có mã SV vẫn phải ra khóa hợp lệ
    new_a, legacy = _uids_for(MON, "he170001")
    new_b, legacy_b = _uids_for(MON, "he170002")
    assert legacy == legacy_b and new_a != new_b              # uid CŨ trùng nhau, uid MỚI tách theo mã SV
    assert "he170001" in new_a and "he170001" not in legacy
    assert _pick_uid(MON, "he170001", frozenset()) == new_a   # lịch chưa có gì -> uid mới
    assert _pick_uid(MON, "he170001", {legacy}) == legacy     # đã có bản cũ CỦA TÔI -> nhận nuôi, không tạo thêm
    assert _current_uids([MON], "he170001", {legacy}) == {legacy}   # prune tính ĐÚNG uid mà sync đẩy
    mine  = {"extendedProperties": {"private": {"fapc": "1", "fapc_owner": "he170001"}}}
    other = {"extendedProperties": {"private": {"fapc": "1", "fapc_owner": "he170002"}}}
    old   = {"extendedProperties": {"private": {"fapc": "1"}}}      # lịch CŨ, chưa gắn nhãn chủ sở hữu
    assert _is_mine(mine, "he170001", False)
    assert not _is_mine(other, "he170001", True)              # KHÔNG BAO GIỜ đụng sự kiện profile khác
    assert _is_mine(old, "he170001", True)                    # profile mặc định nhận lịch cũ
    assert not _is_mine(old, "he170001", False)               # profile có tên thì KHÔNG

# ---- feat20: lọc 1 môn · lịch cả kỳ ----
def test_subjects_resolve_precedence():
    """`grades-detail iap` phải ra ĐÚNG 1 môn: ưu tiên mã khớp đúng > bắt đầu bằng > chứa > TÊN môn.
    Mã trả về phải là mã CHUẨN của server ('FRS401c', KHÔNG phải chữ người dùng gõ) vì nó được GỬI
    NGƯỢC lên FAP ở grades._mark_params. Mơ hồ -> (None, ứng viên) để caller bảo người dùng gõ rõ hơn.
    Resolution must be case-insensitive but return the server's exact casing; ambiguity must not guess."""
    import fapc.core.subjects as S
    codes = ["IAP301", "FRS401c", "FRS402", "MAE101"]
    idx = {"MAE101": {"vi": "Toán rời rạc", "en": "Mathematics for Engineering"},
           "IAP301": {"vi": "", "en": "Information Assurance"}}
    prev = S._INDEX                                   # KHÔNG dùng load() (đọc file) — test phải thuần
    try:
        S.set_index({})
        assert S.resolve("IAP301", codes) == ("IAP301", ["IAP301"])          # khớp đúng
        assert S.resolve("frs401c", codes) == ("FRS401c", ["FRS401c"])       # thường hoá -> mã CHUẨN
        assert S.resolve("mae", codes)[0] == "MAE101"                        # bắt đầu bằng, duy nhất
        assert S.resolve("301", codes)[0] == "IAP301"                        # chứa (không phải tiền tố)
        code, cands = S.resolve("frs", codes)                                # mơ hồ: 2 ứng viên
        assert code is None and cands == ["FRS401c", "FRS402"]
        assert S.resolve("frs402", codes) == ("FRS402", ["FRS402"])          # khớp đúng THẮNG tầng tiền tố
        assert S.resolve("rời rạc", codes, idx)[0] == "MAE101"               # khớp TÊN tiếng Việt
        assert S.resolve("assurance", codes, idx)[0] == "IAP301"             # tên rỗng vi -> dùng en
        assert S.resolve("zzz", codes) == (None, codes)                      # không khớp -> liệt kê cả kỳ
        assert S.resolve("", codes) == (None, codes)                         # rỗng -> liệt kê cả kỳ
        assert S.resolve("iap", []) == (None, [])                            # không có môn nào -> không nổ
        # detail_text hợp nhất 2 nguồn mã bằng phép `not in` PHÂN BIỆT hoa-thường -> có thể lọt mã trùng;
        # trùng lặp mà không khử sẽ biến 1 môn thành "mơ hồ 2 ứng viên".
        assert S.resolve("IAP301", ["IAP301", "iap301"]) == ("IAP301", ["IAP301"])
    finally:
        S._INDEX = prev

def test_grades_detail_only_filter():
    """`grades-detail IAP301` chỉ tải điểm thành phần CỦA 1 MÔN (kỳ 6 môn: 8 request -> 3).
    Môn không tra ra phải LIỆT KÊ môn trong kỳ (đừng im lặng), và kỳ RỖNG vẫn báo 'chưa có dữ liệu điểm'
    — tức bộ lọc phải nằm SAU guard kỳ rỗng, không phải trước.
    Filtering must cut requests, name the alternatives when it fails, and never mask an empty term."""
    import fapc.core.grades as G, fapc.core.courses as C, fapc.core.subjects as S
    saved = (G.fetch_marks, C.fetch_courses, G.call, S._INDEX)
    try:
        S.set_index({})
        G.fetch_marks = lambda *a, **k: [{"subjectCode": "IAP301", "courseID": "2"},
                                         {"subjectCode": "EXE101", "courseID": "3"}]
        C.fetch_courses = lambda *a, **k: [{"subjectCode": "FRS401c", "courseId": "9"},
                                           {"subjectCode": "FRS402", "courseId": "10"}]
        hits = []
        def _call(*a, **k):
            hits.append(1)                               # đếm GetMarkByCourse thật sự phát ra
            return 200, {"data": [{"item": "Assignment", "value": "8.0", "weight": "100%"}]}
        G.call = _call
        full = G.detail_text("t", "FPTU", "HE1", "Summer2026")
        assert len(hits) == 4                                                # nền: cả kỳ = 4 lượt gọi
        assert ("4 môn" in full or "4 subjects" in full)
        hits[:] = []
        one = G.detail_text("t", "FPTU", "HE1", "Summer2026", only="iap")
        assert "IAP301" in one and "EXE101" not in one and "FRS401c" not in one
        assert len(hits) == 1                                                # 4 môn -> 1 lượt gọi
        assert "1 môn" in one or "1 subject" in one
        hits[:] = []
        amb = G.detail_text("t", "FPTU", "HE1", "Summer2026", only="frs")    # mơ hồ -> liệt kê ứng viên
        assert "FRS401c" in amb and "FRS402" in amb and "IAP301" not in amb
        unk = G.detail_text("t", "FPTU", "HE1", "Summer2026", only="zzz999")  # lạ -> liệt kê CẢ kỳ
        assert "IAP301" in unk and "EXE101" in unk and "FRS401c" in unk and "zzz999" in unk
        assert hits == []                                                    # cả 2 ca: KHÔNG gọi mạng
        G.fetch_marks = lambda *a, **k: []
        C.fetch_courses = lambda *a, **k: []
        empty = G.detail_text("t", "FPTU", "HE1", "Summer2026", only="IAP301")
        assert "Chưa có dữ liệu điểm" in empty or "No grades yet" in empty    # KHÔNG phải 'không thấy môn'
    finally:
        G.fetch_marks, C.fetch_courses, G.call, S._INDEX = saved

def test_week_index():
    """Header 'Tuần 5/15': đếm theo tuần LỊCH (mốc thứ 2) nên ngày cùng tuần với ngày khai giảng vẫn là
    tuần 1. Ngoài kỳ -> (None, tổng) để header im lặng bỏ mảnh tuần; thiếu mốc -> (None, None):
    tuyệt đối KHÔNG được in 'Tuần None'. Out-of-term and unknown bounds must both stay renderable."""
    from fapc.core.schedule import week_index
    start, end = datetime.date(2026, 5, 11), datetime.date(2026, 8, 30)   # T2 -> CN, đúng 16 tuần
    assert week_index(start, end, datetime.date(2026, 5, 11)) == (1, 16)  # ngày đầu kỳ
    assert week_index(start, end, datetime.date(2026, 5, 10)) == (None, 16)  # CN TRƯỚC kỳ -> ngoài khoảng
    assert week_index(start, end, datetime.date(2026, 6, 15)) == (6, 16)  # giữa kỳ
    assert week_index(start, end, datetime.date(2026, 8, 30)) == (16, 16)  # ngày cuối kỳ
    assert week_index(start, end, datetime.date(2026, 9, 1)) == (None, 16)  # sau kỳ -> vẫn biết tổng
    assert week_index(start, end, datetime.datetime(2026, 6, 15, 7, 30)) == (6, 16)  # datetime cũng nhận
    # kỳ bắt đầu GIỮA tuần: ngày thứ 2 trước đó vẫn thuộc tuần 1
    assert week_index(datetime.date(2026, 5, 13), end, datetime.date(2026, 5, 11))[0] == 1
    assert week_index(None, end, datetime.date(2026, 6, 15)) == (None, None)   # chưa tra được mốc kỳ
    assert week_index(start, None, datetime.date(2026, 6, 15)) == (None, None)
    assert week_index(end, start, datetime.date(2026, 6, 15)) == (None, None)  # mốc lộn ngược -> không đoán

def test_weekly_pattern():
    """Lịch cả kỳ = vài chục buổi; view mặc định gom thành 'mẫu lặp hằng tuần' + buổi LỆCH mẫu.
    Bộ (thứ, giờ, phòng) lặp >= min_repeat là mẫu; buổi học bù/đổi phòng phải rơi ra 'exceptions'
    chứ không được âm thầm gộp vào mẫu (người dùng sẽ đi nhầm phòng).
    A one-off makeup class must never be absorbed into the repeating pattern."""
    from fapc.core.schedule import weekly_pattern
    mon = datetime.date(2026, 5, 11)
    def _iso(d): return d.strftime("%Y-%m-%d")
    base = []
    for w in range(10):                                     # 10 tuần: T2 sáng + T4 chiều
        d = mon + datetime.timedelta(weeks=w)
        base.append(_sess(_iso(d), "(07:30 - 09:00)", "IAP301"))
        base.append(_sess(_iso(d + datetime.timedelta(days=2)), "(13:00 - 15:00)", "IAP301"))
    pat = weekly_pattern(base)
    assert sorted(r["count"] for r in pat["IAP301"]["repeats"]) == [10, 10]
    assert pat["IAP301"]["exceptions"] == []               # đều đặn -> không có buổi lệch
    assert [r["weekday"] for r in pat["IAP301"]["repeats"]] == [0, 2]   # đã sắp theo thứ (T2, T4)
    # 1 buổi dời sang T5 -> mẫu T4 còn 9 buổi, buổi dời thành exception (KHÔNG mất buổi nào)
    moved = base[:-1] + [_sess(_iso(mon + datetime.timedelta(weeks=9, days=3)), "(13:00 - 15:00)", "IAP301")]
    pat2 = weekly_pattern(moved)
    assert sorted(r["count"] for r in pat2["IAP301"]["repeats"]) == [9, 10]
    assert len(pat2["IAP301"]["exceptions"]) == 1
    assert pat2["IAP301"]["exceptions"][0]["date"] == _iso(mon + datetime.timedelta(weeks=9, days=3))
    # đổi PHÒNG cùng giờ = bộ khác -> lệch mẫu (đừng nói người ta cứ đến phòng cũ)
    other_room = base[:-1] + [_sess(_iso(mon + datetime.timedelta(weeks=9, days=2)), "(13:00 - 15:00)",
                                    "IAP301", room="BE-999")]
    assert len(weekly_pattern(other_room)["IAP301"]["exceptions"]) == 1
    # môn dưới ngưỡng lặp (2 buổi) -> TẤT CẢ là exception, không có mẫu giả
    few = [_sess(_iso(mon), "(07:30 - 09:00)", "EXE101"),
           _sess(_iso(mon + datetime.timedelta(weeks=1)), "(07:30 - 09:00)", "EXE101")]
    p3 = weekly_pattern(few)
    assert p3["EXE101"]["repeats"] == [] and len(p3["EXE101"]["exceptions"]) == 2
    assert weekly_pattern([]) == {} and weekly_pattern([BAD]) == {}   # rỗng / buổi hỏng -> không nổ

def test_semester_text_pattern_and_empty():
    """`/semester` mặc định = mẫu lặp + ghi chú TRUNG THỰC (nguồn cả-kỳ KHÔNG biết buổi huỷ/nghỉ lễ).
    Kỳ SAU thường chưa xếp lịch -> phải báo rõ + gợi ý kỳ xem được, TUYỆT ĐỐI không trả chuỗi rỗng
    (bot gửi tin rỗng = Telegram lỗi 400). A not-yet-published term must still produce a real message."""
    import fapc.app.dashboard as D
    mon = datetime.date(2026, 5, 11)
    sess = [_sess((mon + datetime.timedelta(weeks=w)).strftime("%Y-%m-%d"), "(07:30 - 09:00)", "IAP301")
            for w in range(6)]
    sems = [{"semesterName": "Summer2026", "startDate": "2026-05-11T00:00:00", "endDate": "2026-08-30T00:00:00"},
            {"semesterName": "Fall2026", "startDate": "2026-09-07T00:00:00", "endDate": "2026-12-27T00:00:00"}]
    saved = (D.fetch_sessions, D.fetch_semesters)
    try:
        D.fetch_sessions = lambda *a, **k: sess
        D.fetch_semesters = lambda *a, **k: sems
        txt = D.semester_text("t", "FPTU", "HE1", "Summer2026")           # view mặc định = pattern
        assert "🔁" in txt and "IAP301" in txt and "×6" in txt            # mẫu lặp, không liệt kê 6 dòng
        assert "Summer2026" in txt and "week-exact" in txt                # ghi chú trung thực bắt buộc
        assert "📌" not in txt                                            # pattern KHÔNG in từng ngày
        wks = D.semester_text("t", "FPTU", "HE1", "Summer2026", view="weeks")
        assert wks.count("📌") == 6 and ("Tuần 1 " in wks or "Week 1 " in wks)   # số tuần THẬT của kỳ
        lst = D.semester_text("t", "FPTU", "HE1", "Summer2026", view="list")
        assert lst.count("🕐") == 6 and len(lst) > len(txt)               # liệt kê từng buổi (dài hơn)
        D.fetch_sessions = lambda *a, **k: []                             # kỳ chưa xếp lịch
        empty = D.semester_text("t", "FPTU", "HE1", "Spring2027")
        assert empty.strip() and "Spring2027" in empty and "🚧" in empty
        assert "0 buổi" in empty or "0 sessions" in empty
    finally:
        D.fetch_sessions, D.fetch_semesters = saved
    # gợi ý kỳ khác: cố định 'hôm nay' để test KHÔNG phụ thuộc đồng hồ máy
    sems3 = sems + [{"semesterName": "Spring2027", "startDate": "2027-01-04T00:00:00",
                     "endDate": "2027-04-25T00:00:00"}]
    sug = D.semester_view_text([], "Spring2027", sems=sems3, today=datetime.date(2026, 8, 20))
    line = [l for l in sug.split("\n") if l.lstrip().startswith("📅")]
    assert line and "Fall2026" in line[0] and "Spring2027" not in line[0]   # đừng gợi ý lại chính kỳ vừa hỏi

# ---- runner không cần pytest ----
def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed (tổng {len(tests)})")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(_run())
