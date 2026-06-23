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
    import fapc.core.grades as G
    G.fetch_marks = lambda *a, **k: [{"subjectCode": "PRF192", "courseID": 11},
                                     {"subjectCode": "MAE101", "courseID": None}]
    # courseID 11 -> 1 thành phần (field 'course*' bị lọc); None -> chưa có
    G.call = lambda *a, **k: (200, {"data": [{"courseID": 11, "item": "Assignment", "value": "8.0", "weight": "20%"}]})
    txt = G.detail_text("t", "FPTU", "HE1", "Summer2026")
    assert "PRF192" in txt and "Assignment" in txt and "8.0" in txt and "courseID" not in txt
    assert "MAE101" in txt                                # môn không courseID vẫn liệt kê (chưa có TP)

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
    import fapc.app.bot_core as B, fapc.core.grades as G, fapc.core.extras as E
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
    assert f2 is False and any("Assignment" in e and "8.5" in e for e in ev2)   # vừa có điểm -> báo
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
    assert any("9.0" in e for e in ev)                      # điểm tổng kết 0.0 -> 9.0

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
    assert any("9.0" in e for e in ev2)                              # đổi giá trị thật -> báo

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
