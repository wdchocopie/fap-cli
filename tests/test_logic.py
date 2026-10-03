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
# API v2 là OPT-IN: ghim v1 + XOÁ khoá v2 TRƯỚC khi import fapc (loader .env dùng setdefault -> giá trị đặt ở đây
# THẮNG .env thật). Test v2 tự bật/tắt qua os.environ với khoá GIẢ "test-key" — khoá thật không bao giờ vào test.
os.environ["FAP_API_VERSION"] = "v1"; os.environ["FAP_V2_KEY"] = ""

from fapc.core.schedule import parse_session, build_ics
from fapc.core.grades import _gpa
from fapc.core.whatif import _split, needed_average
from fapc.app.dashboard import _week_bounds, _day_lines
from fapc.fmt import room as fmt_room, safe_float
from fapc.app.notify import _day_digest, _week_digest

# ---- HỢP ĐỒNG OFFLINE: CHẶN mọi lời gọi mạng THẬT (api.fpt.edu.vn / Google / Telegram / Discord) ----
# Chỉ raise thôi là KHÔNG đủ: code hay bọc `except Exception` (vd phần phụ "degrade gracefully") nên lỗi
# bị nuốt âm thầm và test vẫn PASS dù đã bắn request thật lên server trường — đã xảy ra 2 lần (GetSemester ở
# 68c7ada, GetActivityStudent ở /attendance). Vì vậy GHI LẠI mọi lần thử; runner đánh FAIL test làm tăng số đó.
import requests as _rq
_NET_ATTEMPTS = []
def _no_network(url="?", *a, **k):
    # CHỈ ghi HOST: token FAP nằm trong query, nhưng token bot Telegram nằm NGAY TRONG PATH (/bot<TOKEN>/…) và
    # secret webhook Discord cũng trong path — mà process test có nạp .env THẬT, và /update gửi output selftest
    # vào chat. Host là đủ biết đã gọi dịch vụ nào.
    from urllib.parse import urlsplit
    _NET_ATTEMPTS.append(urlsplit(str(url)).netloc or "?")
    raise _rq.ConnectionError("offline test: real network call blocked")
_rq.get = _rq.post = _no_network
_rq.request = lambda method, url, *a, **k: _no_network(url)
_rq.Session.request = lambda self, method, url, *a, **k: _no_network(url)

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
    B.fetch_sessions = lambda *a, **k: []           # /banrisk nay đọc lịch (môn chưa điểm danh) -> stub, giữ OFFLINE
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

# ---- B1: lõi API cứng hơn — lỗi phiên kiểu v2 · cảnh báo v1 dời route · một bộ chọn học kỳ ----
def test_check_auth_v2_style_session_errors():
    """Thân kiểu API v2 (myFAP 2.0.5 `_isSessionExpired`) BỌC trong HTTP 200 -> hết phiên, KHÔNG thành [] im lặng."""
    from fapc.core.api import check_auth, _EXPIRED_MSG
    def _msg(fn):
        try: fn()
        except SystemExit as e: return str(e)
        return None
    assert _msg(lambda: check_auth(200, {"code": "401", "data": None})) == _EXPIRED_MSG          # code chuỗi
    assert _msg(lambda: check_auth(200, {"code": 401, "data": None})) == _EXPIRED_MSG            # code số (app so lỏng ==)
    assert _msg(lambda: check_auth(200, {"code": "200", "errorMessage": "Unauthorized"})) == _EXPIRED_MSG
    assert _msg(lambda: check_auth(200, {"errorMessage": "  unauthorized \n"})) == _EXPIRED_MSG   # strip + hoa/thường
    # HTTP 500 KHÔNG phải hết phiên (app đăng xuất khi 500; fap-cli làm vậy = vòng refresh vô ích)
    assert not _raises_exit(lambda: check_auth(500, "<html>Server Error</html>"))
    assert not _raises_exit(lambda: check_auth(500, {"message": "Internal error"}))
    # thân BÌNH THƯỜNG giữ nguyên hành vi (shape thật v1: code chuỗi '200', errorMessage None)
    assert not _raises_exit(lambda: check_auth(200, {"message": "ok", "code": "200", "errorMessage": None, "data": []}))
    assert not _raises_exit(lambda: check_auth(200, {"code": "200", "errorMessage": "Unauthorized access log"}))
    assert not _raises_exit(lambda: check_auth(200, {"code": True, "data": []}))       # bool KHÔNG phải 401
    assert not _raises_exit(lambda: check_auth(200, [{"code": "401"}]))                 # list dữ liệu, không phải envelope
    assert not _raises_exit(lambda: check_auth(None, "Lỗi mạng (ConnectionError) khi gọi X"))
    # code '201' GIỮ NGUYÊN ngữ nghĩa: token -> hết phiên; checksum -> thông điệp checksum; khác -> từ chối chung
    assert _msg(lambda: check_auth(200, {"code": "201", "message": "Token invalid"})) == _EXPIRED_MSG
    assert "checksum" in _msg(lambda: check_auth(200, {"code": "201", "message": "Thông tin checksum không chính xác"}))
    assert "code 201" in _msg(lambda: check_auth(200, {"code": "201", "message": "Thành công"}))

def test_is_session_expired_table():
    """Luật hết-phiên DÙNG CHUNG (cho nơi không muốn raise: watcher, conduct) khớp đúng các ca check_auth raise _EXPIRED_MSG."""
    from fapc.core.api import is_session_expired as X
    assert X(401, {}) and X(403, "") and X(200, {"code": "401"}) and X(200, {"errorMessage": "Unauthorized"})
    assert X(200, {"code": "201", "message": "Token invalid"})
    assert not X(200, {"code": "201", "message": "Thông tin checksum không chính xác"})   # checksum ≠ hết phiên
    assert not X(200, {"code": "201", "message": "Thành công", "data": None})             # conduct 201-null ≠ hết phiên
    assert not X(500, {}) and not X(500, "<html/>") and not X(None, "Lỗi mạng")
    assert not X(200, {"code": "200", "data": []}) and not X(404, {"Message": "No HTTP resource"})

def test_classify_drift_table():
    """Bảng phân loại THUẦN: chỉ tín hiệu mức route. 404 CÓ thân JSON (GeFeeByRoll/GetCourseOfSemester) KHÔNG phải drift."""
    from fapc.core.api import classify_drift as C
    for code in (301, 302, 303, 307, 308):
        assert C(code, "") == "redirect", code
    assert C("302", None) == "redirect"                                       # mã dạng chuỗi vẫn đọc được
    assert C(410, '{"Message": "gone"}') == "gone"
    assert C(404, "<!DOCTYPE html><html><body>404 - File or directory not found.</body></html>") == "not_found"
    assert C(404, "") == "not_found" and C(404, "   ") == "not_found" and C(404, None) == "not_found"
    assert C(404, '{"Message": "x"}', "text/html; charset=utf-8") == "not_found"   # server tự nhận là HTML
    # 404 + JSON = lỗi dữ liệu của endpoint, KHÔNG phải route biến mất
    assert C(404, {"Message": "No fee"}) is None                              # call() đã parse JSON
    assert C(404, '{"Message": "No fee"}', "application/json; charset=utf-8") is None
    assert C(404, b'{"Message": "No fee"}') is None
    for code in (200, 201, 400, 401, 403, 500, 502, 503):
        assert C(code, "<html>whatever</html>") is None, code
    assert C(None, "Lỗi mạng (ConnectionError) khi gọi X") is None and C("abc", "") is None

def test_drift_hint_once_per_process_no_token_leak():
    """call() soi CHÍNH phản hồi nhận được (0 request thêm): tín hiệu đầu tiên -> ĐÚNG 1 gợi ý song ngữ ra stderr;
    không bao giờ in URL/token; 404-HTML của endpoint vốn đã 404 (GetSemesterMark) không báo động giả."""
    import fapc.core.api as A
    class _R:
        def __init__(self, code, text, js=None, ctype="text/html"):
            self.status_code, self.text, self._js, self.headers = code, text, js, {"Content-Type": ctype}
        def json(self):
            if self._js is None: raise ValueError("not json")
            return self._js
    seq, n = [], {"c": 0}
    def fake_get(url, **k):
        n["c"] += 1
        return seq.pop(0)
    orig, saved = A.requests.get, dict(A._DRIFT_WARNED)
    err = io.StringIO()
    try:
        A._CACHE.clear(); A._DRIFT_WARNED["done"] = False
        A.requests.get = fake_get
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            seq[:] = [_R(404, "", js={"Message": "No fee"}, ctype="application/json")]      # 404 + JSON -> im
            A.call("GeFeeByRoll", [("Authen", "SECRETTOKEN123")], "HE000000", "FPTU")
            seq[:] = [_R(404, "<html>404</html>")]                                         # đã-biết-404 -> im
            A.call("GetSemesterMark", [("Authen", "SECRETTOKEN123")], "HE000000", "FPTU", checksum_value=False)
            assert err.getvalue() == "" and not A._DRIFT_WARNED["done"], err.getvalue()
            seq[:] = [_R(302, "")]                                                         # tín hiệu thật -> in 1 lần
            http, _ = A.call("GetStudentMark", [("Authen", "SECRETTOKEN123")], "HE000000", "FPTU")
            seq[:] = [_R(410, ""), _R(404, "<html/>")]
            A.call("GetActivityStudent", [("Authen", "SECRETTOKEN123")], "HE000000", "FPTU")
            A.call("GetStudentMark", [("Authen", "SECRETTOKEN123")], "HE000000", "FPTU")
        out = err.getvalue()
        assert http == 302 and n["c"] == 5                   # 0 request thêm (302 không retry, không theo redirect)
        assert out.count("docs/21-api-v2.md") == 2 and out.count("⚠️") == 2, out   # 1 gợi ý = 1 dòng VI + 1 dòng EN
        assert "GetStudentMark" in out and "302" in out and "FAP_API_VERSION" in out
        assert "API v2" in out and "chuyển sang" in out and "moved to" in out           # song ngữ
        assert "SECRETTOKEN123" not in out and "Authen" not in out and "://" not in out and "checksum=" not in out
        assert not seq                                        # đã dùng đúng 5 phản hồi giả
    finally:
        A.requests.get = orig; A._CACHE.clear(); A._DRIFT_WARNED.update(saved)

def test_warn_drift_pure_once():
    """_warn_drift: lý do None -> không in; lần ĐẦU có lý do -> in; mọi lần sau -> im; 30x trên endpoint đã-biết-404 VẪN tính."""
    import fapc.core.api as A
    saved = dict(A._DRIFT_WARNED)
    try:
        A._DRIFT_WARNED["done"] = False
        with contextlib.redirect_stderr(io.StringIO()) as e:
            assert A._warn_drift("X", 200, None) is False
            assert A._warn_drift("GetSemesterMark", 404, "not_found") is False
            assert A._warn_drift("GetSemesterMark", 301, "redirect") is True
            assert A._warn_drift("Y", 410, "gone") is False
        assert e.getvalue().count("GetSemesterMark") == 2       # dòng VI + dòng EN của CÙNG 1 gợi ý
    finally:
        A._DRIFT_WARNED.update(saved)

def _sems(*rows):
    """GetSemester giả, shape THẬT ('YYYY-MM-DDT00:00:00', tăng dần theo startDate như server trả)."""
    return [{"semesterName": n, "termID": str(i), "campusID": "1", "startDate": a + "T00:00:00", "endDate": b + "T00:00:00"}
            for i, (n, a, b) in enumerate(rows)]

_YEAR = _sems(("Spring2026", "2026-01-05", "2026-04-25"), ("Summer2026", "2026-05-04", "2026-08-29"),
              ("Fall2026", "2026-09-07", "2026-12-26"), ("Spring2027", "2027-01-04", "2027-04-24"))

def test_select_semester_in_term_and_gaps():
    """Đúng màn hình chính myFAP 2.0.5: trong kỳ -> kỳ đó; khe giữa 2 kỳ -> kỳ có ngày BẮT ĐẦU gần nhất (2 phía)."""
    from fapc.core.api import select_semester as S
    dt = datetime.datetime
    assert S(_YEAR, dt(2026, 10, 3, 9, 0)) == "Fall2026"
    assert S(_YEAR, dt(2026, 9, 7, 0, 0)) == "Fall2026"                     # 00:00 ngày đầu kỳ: trong kỳ
    # khe cuối tháng 8 (29/08 → 07/09): kỳ sau bắt đầu gần hơn HẲN kỳ trước (04/05) -> Fall
    assert S(_YEAR, dt(2026, 8, 31, 12, 0)) == "Fall2026"
    assert S(_YEAR, dt(2026, 9, 6, 23, 59)) == "Fall2026"
    # khe cuối tháng 12 (26/12 → 04/01): Spring năm SAU, KHÔNG phải Fall theo tháng như default_semester
    assert S(_YEAR, dt(2026, 12, 30, 8, 0)) == "Spring2027"
    assert S(_YEAR, datetime.date(2027, 1, 2)) == "Spring2027"
    # trước kỳ đầu tiên / sau kỳ cuối cùng -> vẫn ra kỳ gần nhất (không None)
    assert S(_YEAR, dt(2025, 11, 1)) == "Spring2026" and S(_YEAR, dt(2028, 1, 1)) == "Spring2027"

def test_select_semester_last_day_of_term_like_app():
    """Ngày CUỐI kỳ: app so THỜI ĐIỂM `new Date()` với `new Date('…T00:00:00')` -> từ sau 00:00 ngày cuối đã
    KHÔNG còn 'trong kỳ' -> kỳ bắt đầu gần nhất (kỳ sau). Đúng 00:00 (hoặc truyền date) vẫn là kỳ cũ."""
    from fapc.core.api import select_semester as S
    from fapc.core.schedule import pick_semester as P
    assert S(_YEAR, datetime.datetime(2026, 8, 29, 0, 0)) == "Summer2026"   # đúng mốc endDate: còn trong kỳ
    assert S(_YEAR, datetime.date(2026, 8, 29)) == "Summer2026"             # date = 00:00 ngày đó
    assert S(_YEAR, datetime.datetime(2026, 8, 29, 10, 0)) == "Fall2026"    # sau 00:00 ngày cuối -> như app
    # pick_semester (dashboard) và current_semester GIỜ CÙNG MỘT luật — trước đây lệch đúng ở ngày này
    for when in (datetime.datetime(2026, 8, 29, 10, 0), datetime.date(2026, 8, 29), datetime.datetime(2026, 12, 30)):
        assert P(_YEAR, when) == S(_YEAR, when), when

def test_select_semester_overlap_ties_and_order():
    """Chồng lấn -> kỳ ĐẦU TIÊN theo thứ tự server (app dùng find). Hoà khoảng cách -> giữ kỳ đứng TRƯỚC (reduce '<' hẳn)."""
    from fapc.core.api import select_semester as S
    ov = _sems(("Summer2026", "2026-05-04", "2026-08-29"), ("Bridge2026", "2026-08-01", "2026-09-30"))
    assert S(ov, datetime.datetime(2026, 8, 10)) == "Summer2026"                  # cả 2 chứa -> kỳ đứng trước
    assert S(list(reversed(ov)), datetime.datetime(2026, 8, 10)) == "Bridge2026"
    assert S(ov, datetime.datetime(2026, 9, 15)) == "Bridge2026"                  # chỉ 1 kỳ chứa
    tie = _sems(("A2026", "2026-01-01", "2026-01-10"), ("B2026", "2026-03-01", "2026-03-31"))
    mid = datetime.datetime(2026, 1, 1) + (datetime.datetime(2026, 3, 1) - datetime.datetime(2026, 1, 1)) / 2
    assert S(tie, mid) == "A2026" and S(list(reversed(tie)), mid) == "B2026"      # hoà (ở khe) -> phần tử đứng trước

def test_select_semester_empty_and_malformed():
    """Rỗng / toàn ngày lỗi -> None (caller tự fallback). 1 kỳ ngày lỗi KHÔNG kéo sập cả lượt dò."""
    from fapc.core.api import select_semester as S
    now = datetime.datetime(2026, 10, 3)
    assert S([], now) is None and S(None, now) is None
    assert S([None, "x", 3, {"semesterName": ""}, {"startDate": "2026-09-07"}], now) is None
    bad = {"semesterName": "Bad", "startDate": "NOT-A-DATE", "endDate": None}
    assert S([bad], now) is None
    half = {"semesterName": "Half", "startDate": "2026-09-07T00:00:00", "endDate": "??"}   # end lỗi: không 'trong kỳ'
    assert S([bad, half], now) == "Half"                                            # nhưng vẫn dự thi 'gần nhất'
    assert S([bad] + _YEAR, now) == "Fall2026"
    # các shape ngày khác vẫn đọc được (cùng thứ tự format với schedule.parse_date)
    alt = [{"semesterName": "Fall2026", "startDate": "09/07/2026", "endDate": "2026-12-26"}]
    assert S(alt, now) == "Fall2026"

def test_current_semester_uses_shared_picker_and_contract():
    """current_semester: FAP_SEMESTER > GetSemester (select_semester) > default_semester; LUÔN chuỗi, KHÔNG raise."""
    import fapc.core.api as A
    class _R:
        status_code = 200
        def __init__(s, js): s._js = js
        def json(s): return s._js
    orig_sem = os.environ.get("FAP_SEMESTER"); orig_get, orig_now = A.requests.get, A._vn_now
    try:
        os.environ.pop("FAP_SEMESTER", None); A._CACHE.clear()
        A._vn_now = lambda: datetime.datetime(2026, 12, 30, 9, 0, tzinfo=datetime.timezone.utc)   # khe cuối năm
        A.requests.get = lambda url, **k: _R({"code": "200", "errorMessage": None, "data": _YEAR})
        with contextlib.redirect_stderr(io.StringIO()):
            assert A.current_semester("tok", "FPTU", "HE000000") == "Spring2027"    # cũ: default -> 'Fall2026'
        A.requests.get = lambda url, **k: _R({"code": "200", "data": []})           # rỗng -> đoán theo ngày
        assert A.current_semester("tok", "FPTU", "HE000000") == "Fall2026"
        err = io.StringIO()
        A.requests.get = lambda url, **k: _R({"code": "401", "errorMessage": "Unauthorized", "data": None})
        with contextlib.redirect_stderr(err):                                       # hết phiên kiểu v2 -> cảnh báo + default
            assert A.current_semester("tok", "FPTU", "HE000000") == "Fall2026"
        assert "FAP_SEMESTER" in err.getvalue()
        def boom(url, **k): raise RuntimeError("weird")
        A.requests.get = boom                                                       # lỗi lạ -> vẫn chuỗi, không raise
        assert A.current_semester("tok", "FPTU", "HE000000") == "Fall2026"
        os.environ["FAP_SEMESTER"] = "Summer2030"
        assert A.current_semester("tok", "FPTU", "HE000000") == "Summer2030"
    finally:
        A.requests.get, A._vn_now = orig_get, orig_now; A._CACHE.clear()
        if orig_sem is None: os.environ.pop("FAP_SEMESTER", None)
        else: os.environ["FAP_SEMESTER"] = orig_sem

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
    txt = E.profile_text("t", "FPTU", "HE1", full=True)                      # CLI
    assert "Nguyễn Văn A" in txt and "HE190000" in txt and "15/09/2004" in txt and "Nam" in txt
    assert "CCCD" not in txt                                                 # field rỗng -> KHÔNG hiện

def test_profile_chat_hides_private_fields():
    """Chat (mặc định) KHÔNG được chứa ngày sinh / SĐT / CCCD dù server có trả; CLI (full=True) thì có."""
    import fapc.core.extras as E
    import fapc.app.bot_core as B
    rec = {"fullname": "Nguyễn Văn A", "rollNumber": "HE000000", "email": "x@example.com",
           "dateOfBirth": "2004-09-15T00:00:00", "gender": True, "statusCode": "HD",
           "mobilePhone": "0900000000", "iDCard": "000000000001"}
    saved = (E.fetch_profile, B.creds, B.current_semester)
    try:
        E.fetch_profile = lambda *a, **k: [dict(rec)]
        B.creds = lambda: ("t", "FPTU", "HE000000")
        B.current_semester = lambda *a, **k: "Fall2026"
        for chat in (E.profile_text("t", "FPTU", "HE000000"), B.handle("profile")):
            assert "Nguyễn Văn A" in chat and "x@example.com" in chat
            for secret in ("15/09/2004", "0900000000", "000000000001"):
                assert secret not in chat, secret
            assert "fap profile" in chat                                    # chỉ đường xem ở máy
        cli = E.profile_text("t", "FPTU", "HE000000", full=True)
        assert all(s in cli for s in ("15/09/2004", "0900000000", "000000000001"))
        assert "🔒" not in cli
    finally:
        E.fetch_profile, B.creds, B.current_semester = saved

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

# ---- feat: Google Calendar trong chat + nhiều đích (multi-Google) ----
def test_gcal_norm_label():
    """Nhãn đích: rỗng -> "" (mặc định); chữ/số/._- hợp lệ; tên nguy hiểm / trùng file sổ đăng ký -> raise."""
    from fapc.app.gcal import norm_label
    assert norm_label("") == "" and norm_label("  ") == "" and norm_label(None) == ""
    assert norm_label("work") == "work" and norm_label("a.b-c_d") == "a.b-c_d"
    # từ khoá cờ (prune/yes/force + bí danh VN) bị CẤM làm nhãn -> parse_sync_args không mơ hồ
    for bad in ("..", ".", "destinations", "gcal_token", "a/b", "a b", "wörk", "x\\y",
                "prune", "yes", "force", "dọn", "có", "ép"):
        try:
            norm_label(bad); assert False, f"nhãn {bad!r} phải bị từ chối"
        except ValueError:
            pass

def test_gcal_concrete_and_dupe_guard():
    """CHỐT AN TOÀN multi-Google: hai nhãn KHÔNG được trỏ CÙNG một calendar_id CỤ THỂ (prune xóa chéo).
    'primary' là tương đối theo tài khoản nên KHÔNG bị coi là trùng (nhiều tài khoản, mỗi cái 1 primary)."""
    from fapc.app import gcal as G
    assert not G._is_concrete("primary") and not G._is_concrete("") and not G._is_concrete(None)
    assert G._is_concrete("me@gmail.com") and G._is_concrete("x@group.calendar.google.com")
    t = {"": "primary", "work": "primary", "a": "x@g.com", "b": "x@g.com", "c": "y@g.com"}
    assert G._dupe_of("work", t) == []                        # primary lặp -> KHÔNG trùng (khác tài khoản)
    assert set(G._dupe_of("a", t)) == {"b"} and set(G._dupe_of("b", t)) == {"a"}   # cùng id cụ thể -> trùng
    assert G._dupe_of("c", t) == [] and G._dupe_of("", t) == []

def _with_tmp_registry(fn):
    """Chạy fn() với G.REGISTRY trỏ vào file tạm (KHÔNG đụng output/ thật), rồi dọn sạch."""
    import tempfile, shutil, os as _os
    from fapc.app import gcal as G
    d = tempfile.mkdtemp()
    old = G.REGISTRY
    G.REGISTRY = _os.path.join(d, "destinations.json")
    try:
        fn(G)
    finally:
        G.REGISTRY = old
        shutil.rmtree(d, ignore_errors=True)

def test_gcal_registry_add_remove():
    """calendar-add/-remove: đăng ký đích có nhãn, đòi calendar_id CỤ THỂ, từ chối trùng lịch."""
    def body(G):
        assert G.add_destination("work", "work@gmail.com").startswith("✓")
        assert G._load_registry() == {"work": {"calendar_id": "work@gmail.com"}}
        assert "⛔" in G.add_destination("home", "work@gmail.com")     # trùng calendar_id cụ thể -> từ chối
        prim = G.add_destination("home", "primary").lower()
        assert "primary" in prim or "concrete" in prim or "cụ thể" in prim   # 'primary' cho nhãn có tên -> từ chối
        assert G.add_destination("home", "home@group.calendar.google.com").startswith("✓")
        for bad in ("bad label", "..", "destinations"):
            assert "⛔" in G.add_destination(bad, "z@g.com")
        deflt = G.add_destination("", "z@g.com")
        assert "mặc định" in deflt or "default" in deflt
        rows = {lbl: cid for lbl, cid, _a, _d in G.list_destinations()}
        assert rows[""] and rows["work"] == "work@gmail.com" and rows["home"].endswith("group.calendar.google.com")
        assert G.list_destinations()[0][0] == ""                      # đích mặc định đứng đầu
        assert G.remove_destination("work").startswith("✓") and "work" not in G._load_registry()
    _with_tmp_registry(body)

def test_gcal_check_no_dupe_raises():
    """_check_no_dupe: nếu sổ đăng ký (bằng tay/lỗi) có 2 nhãn chung 1 lịch cụ thể -> SystemExit trước khi sync."""
    def body(G):
        G._save_registry({"a": {"calendar_id": "dup@g.com"}, "b": {"calendar_id": "dup@g.com"}})
        for lbl in ("a", "b"):
            try:
                G._check_no_dupe(lbl); assert False, "phải từ chối khi trùng lịch"
            except SystemExit as e:
                assert "dup@g.com" in str(e)
        G._save_registry({"a": {"calendar_id": "one@g.com"}, "b": {"calendar_id": "two@g.com"}})
        G._check_no_dupe("a"); G._check_no_dupe("b")                  # khác lịch -> không nổ
    _with_tmp_registry(body)

def test_gcal_dupe_case_insensitive():
    """calendar_id là email/lịch -> KHÔNG phân biệt hoa-thường & khoảng trắng: 'Me@Gmail.com' == ' me@gmail.com '.
    Nếu so-chuỗi thô thì hai nhãn cùng một lịch (khác hoa-thường) lọt guard -> prune xóa chéo."""
    from fapc.app import gcal as G
    t = {"a": "Me@Gmail.com", "b": " me@gmail.com "}
    assert G._dupe_of("a", t) == ["b"] and G._dupe_of("b", t) == ["a"]
    def body(G):
        assert G.add_destination("a", "Me@Gmail.com").startswith("✓")
        assert "⛔" in G.add_destination("b", "me@gmail.com")         # cùng lịch (khác hoa-thường) -> từ chối
    _with_tmp_registry(body)

def test_gcal_registry_skips_corrupt_entry():
    """HIGH: một dòng sổ đăng ký có value KHÔNG phải dict (sửa tay / ghi dở) KHÔNG được làm sập
    _all_targets/destinations_text (nếu không, /calendar-list ném AttributeError giết cả bot Telegram)."""
    import json as _json
    def body(G):
        with open(G.REGISTRY, "w", encoding="utf-8") as f:           # value là CHUỖI, không phải {"calendar_id":…}
            _json.dump({"work": "cal@g.com", "ok": {"calendar_id": "a@g.com"}}, f)
        assert G._load_registry() == {"ok": {"calendar_id": "a@g.com"}}   # mục hỏng bị bỏ
        G._all_targets(); G.destinations_text()                       # KHÔNG được ném
        assert G._calendar_id("ok") == "a@g.com"
    _with_tmp_registry(body)

def test_gcal_prune_legacy_scope():
    """MEDIUM (đa-người-dùng): prune trên lịch CỤ THỂ (có thể DÙNG CHUNG) KHÔNG được nhận lịch cũ chưa
    gắn dấu (fapc=1 không fapc_owner) — kẻo xóa nhầm sự kiện cũ của SINH VIÊN KHÁC. Chỉ 'primary' cá
    nhân mới nhận lịch cũ. Kiểm bằng cách theo dõi bộ lọc mà _prune yêu cầu server."""
    from fapc.app import gcal as G
    class _Ev:
        def __init__(self, rec): self.rec = rec
        def list(self, **kw): self.rec.append(kw.get("privateExtendedProperty")); return self
        def execute(self): return {"items": []}
    class _Svc:
        def __init__(self): self.rec = []
        def events(self): return _Ev(self.rec)
    concrete = _Svc()
    G._prune(concrete, [], "he170001", "team@group.calendar.google.com", log=lambda *_: None)
    assert concrete.rec == ["fapc_owner=he170001"]               # lịch cụ thể: KHÔNG hỏi trang fapc=1 (lịch cũ)
    prim = _Svc()
    G._prune(prim, [], "he170001", "primary", log=lambda *_: None)
    assert "fapc=1" in prim.rec                                   # primary cá nhân: MỚI nhận lịch cũ chưa gắn dấu

def test_gcal_looks_like_gredirect_beats_fap():
    """Định tuyến DÁN: URL loopback Google phải được nhận DIỆN, và nó cũng khớp mẫu FAP -> phải xét
    Google TRƯỚC (bằng host 127.0.0.1) kẻo tin Google bị đẩy nhầm sang luồng /login."""
    from fapc.app.gcal import looks_like_gredirect
    from fapc.core.auth import looks_like_redirect
    g = "http://127.0.0.1/?state=s&code=4/abc&scope=cal"
    assert looks_like_gredirect(g) and looks_like_gredirect("http://localhost/?error=access_denied")
    assert looks_like_gredirect("4/0Aeanabc-xyz")                # mã Google TRẦN (dán mỗi code) -> vẫn xoá
    assert looks_like_redirect(g)                                # FAP cũng khớp -> chứng minh vì sao phải xét Google trước
    assert not looks_like_gredirect("io.identityserver.demo://cb?code=x")   # redirect FAP -> KHÔNG phải Google
    assert not looks_like_gredirect("hôm nay có lịch gì") and not looks_like_gredirect("")

def test_gcal_auth_finish_needs_session():
    """gcal_auth_finish khi CHƯA mở phiên (không có .gcal_oauth.json) -> SystemExit sạch, KHÔNG chạm google lib."""
    import tempfile, os as _os
    from fapc.app import gcal as G
    old = G.OAUTH_STATE
    G.OAUTH_STATE = _os.path.join(tempfile.gettempdir(), "fapc_test_nope_%d.json" % _os.getpid())
    try:
        G.gcal_auth_finish("http://127.0.0.1/?code=x"); assert False
    except SystemExit as e:
        assert "calendar-auth" in str(e)
    finally:
        G.OAUTH_STATE = old

def test_botgcal_parse_sync_args():
    from fapc.app.botgcal import parse_sync_args
    assert parse_sync_args("") == ("", False, False, False)
    assert parse_sync_args("work") == ("work", False, False, False)
    assert parse_sync_args("prune yes") == ("", True, True, False)
    assert parse_sync_args("home force") == ("home", False, False, True)
    assert parse_sync_args("dọn có") == ("", True, True, False)   # bí danh tiếng Việt

def test_botgcal_auth_session_busy_and_expiry():
    """GcalAuthSession: giữ 1 phiên (chặn phiên thứ 2 khi đang bận), tự nhả sau PASTE_TTL."""
    import time as _t
    from fapc.app import gcal as G
    from fapc.app import botgcal as B
    old_url, old_fin = G.gcal_auth_url, G.gcal_auth_finish
    G.gcal_auth_url = lambda label="": ("http://auth-url", G.norm_label(label))
    try:
        s = B.GcalAuthSession()
        ok, text = s.start("work")
        assert ok and s.busy and s.waiting_paste() and "http://auth-url" in text
        ok2, text2 = s.start("home")                             # đang bận -> phiên 2 bị chặn
        assert not ok2 and "⏳" in text2
        s.started = _t.time() - (B.PASTE_TTL + 5)                 # giả lập quá hạn
        ok3, _ = s.start("home")
        assert ok3 and s.label == "home"                         # phiên cũ tự nhả -> mở phiên mới
        G.gcal_auth_finish = lambda pasted, label=None: "OK " + str(label)
        done_ok, done_msg = B.finish_paste(s, "http://127.0.0.1/?code=x")
        assert done_ok and "OK home" in done_msg and not s.busy  # xong -> nhả phiên
    finally:
        G.gcal_auth_url, G.gcal_auth_finish = old_url, old_fin

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

# ---- feat: link Meet cho buổi ONLINE (thông báo + nhắc tiết) ----
# Dữ liệu THẬT (đo trên dump): `meetURL` là MÃ PHÒNG Meet TRẦN 'abc-defg-hij', KHÔNG phải URL; mỗi lớp
# có đúng 1 mã nhưng FAP chỉ gắn vào vài buổi; mã gắn cả vào buổi học tại phòng.
_CODE, _URL = "abc-defg-hij", "https://meet.google.com/abc-defg-hij"

def test_meet_url_shapes():
    """fmt.meet_url: mã trần -> link Meet; nhận 'meet.google.com/…' thiếu scheme và URL đầy đủ; bỏ rác;
    CHỈ buổi online (mã Meet gắn cả buổi tại phòng nhưng người dùng chỉ cần link cho buổi online)."""
    from fapc.fmt import meet_url
    on = lambda v, k="meetURL": dict(_sess("06/15/2026", "(07:30 - 09:00)", "EXE101", online="true"), **{k: v})
    assert meet_url(on(_CODE)) == _URL                                       # dạng FAP đang trả
    assert meet_url(on("ABC-DEFG-HIJ")) == _URL                              # hoa -> thường
    assert meet_url(on("  " + _CODE + "\n")) == _URL                         # khoảng trắng bao quanh
    assert meet_url(on("meet.google.com/" + _CODE)) == _URL                  # thiếu scheme
    assert meet_url(on("https://zoom.us/j/123")) == "https://zoom.us/j/123"  # URL đầy đủ giữ nguyên
    assert meet_url(on("https://us02web.zoom.us/j/9?pwd=Ab1")) == "https://us02web.zoom.us/j/9?pwd=Ab1"  # subdomain
    teams = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_X%40thread.v2/0?context=%7b%7d"
    assert meet_url(on(teams)) == teams
    assert meet_url(on("HTTPS://meet.google.com/" + _CODE)) == _URL          # chữ hoa ở scheme -> chuẩn hoá
    assert meet_url(on(_CODE, k="meeturl")) == _URL                          # bí danh chữ thường của app
    for junk in ("", "N/A", "null", "abc-def-ghi", "abcdefghij", "javascript:alert(1)", None,
                 "https://x.y/a\n  b",                                       # có khoảng trắng -> BỎ, không cắt bớt
                 "http://meet.google.com/" + _CODE,                          # không phải https
                 "https://example.com/abc",                                  # host không phải phòng họp
                 "https://evilzoom.us/j/1", "https://zoom.us.evil.com/j/1"): # giả host
        assert meet_url(on(junk)) == "", junk
    # REVIEW (bảo mật): chuỗi server chèn link mạo danh / mention NGAY SAU nhãn 'Vào lớp' -> không hiện gì
    for inj in ("https://meet.google.com/" + _CODE + " [Vào lớp](https://evil.example) @everyone",
                "meet.google.com/x [a](https://evil.example)",
                "https://meet.google.com/" + _CODE + ")[x](https://evil.example",
                "https://meet.google.com/<@123>", "https://meet.google.com/a*b|c"):
        assert meet_url(on(inj)) == "", inj
    inperson = dict(_sess("06/15/2026", "(07:30 - 09:00)", "CES202"), meetURL=_CODE)
    assert meet_url(inperson) == ""                                          # buổi tại phòng -> KHÔNG link

def test_meet_line_and_with_meet():
    from fapc.fmt import meet_line, with_meet
    s = dict(_sess("06/15/2026", "(07:30 - 09:00)", "EXE101", online="true"), meetURL=_CODE)
    assert meet_line(s) == "🔗 " + _URL
    assert meet_line(s, indent="   ", label="Join: ") == "   🔗 Join: " + _URL
    assert with_meet("LINE", s, indent="  ") == "LINE\n  🔗 " + _URL          # link ở DÒNG RIÊNG
    assert with_meet("LINE", MON) == "LINE" and meet_line(MON) == ""           # không link -> nguyên văn

def test_fill_meet_inherits_per_class():
    """schedule.fill_meet: buổi thiếu mã MƯỢN mã của CHÍNH lớp (môn+nhóm) — chỉ khi lớp có ĐÚNG 1 mã."""
    from fapc.core.schedule import fill_meet
    a1 = dict(_sess("06/15/2026", "(07:30 - 09:00)", "EXE101", online="true"), meetURL=_CODE)
    a2 = _sess("06/22/2026", "(07:30 - 09:00)", "EXE101", online="true")       # online, KHÔNG mã
    other_grp = dict(_sess("06/16/2026", "(07:30 - 09:00)", "EXE101", online="true"), groupName="OTHER")
    b1 = dict(_sess("06/17/2026", "(07:30 - 09:00)", "HOD402"), meetURL="aaa-bbbb-ccc")
    b2 = dict(_sess("06/18/2026", "(07:30 - 09:00)", "HOD402"), meetURL="ddd-eeee-fff")
    b3 = _sess("06/19/2026", "(07:30 - 09:00)", "HOD402", online="true")       # lớp có 2 mã -> mơ hồ
    nosubj = {"date": "06/20/2026", "slotTime": "(07:30 - 09:00)", "isOnline": "true"}
    src = [a1, a2, other_grp, b1, b2, b3, nosubj, "not-a-dict"]
    out = fill_meet(src)
    assert len(out) == len(src) and out[0] is a1                               # giữ thứ tự, không đụng buổi đã có mã
    assert out[1]["meetURL"] == _CODE and "meetURL" not in a2                  # được điền — dict GỐC không bị sửa
    assert not out[2].get("meetURL")                                           # KHÁC nhóm -> không mượn
    assert not out[5].get("meetURL")                                           # lớp 2 mã -> không đoán
    assert out[6] is nosubj and out[7] == "not-a-dict"                         # thiếu môn / không phải dict -> để nguyên
    assert fill_meet([]) == []

def test_reminder_text_meet_link():
    """Nhắc tiết (Telegram/Discord): buổi online -> dòng '🔗 Vào lớp: <link>' RIÊNG ở cuối; tại phòng -> không."""
    from fapc.app.reminders import reminder_text
    start, end = datetime.datetime(2026, 6, 24, 7, 30), datetime.datetime(2026, 6, 24, 9, 0)
    s = dict(_sess("06/24/2026", "(07:30 - 09:00)", "EXE101", online="true"), meetURL=_CODE)
    txt = reminder_text(start, end, s, 15)
    last = txt.split("\n")[-1]
    assert last.startswith("🔗 ") and last.endswith(_URL)                      # link đứng riêng, ở CUỐI dòng
    assert "EXE101" in txt and "💻 Online" in txt and "GV" in txt
    inperson = dict(_sess("06/24/2026", "(07:30 - 09:00)", "CES202", room="BE-304"), meetURL=_CODE)
    assert "🔗" not in reminder_text(start, end, inperson, 15)

def test_digests_meet_link_and_session_count():
    """Lịch ngày/tuần có link Meet ở dòng riêng; _day_lines vẫn MỘT phần tử/buổi (status() in len() = số buổi)."""
    online = dict(_sess("06/15/2026", "(09:10 - 10:40)", "EXE101", online="true"), meetURL=_CODE)
    day = datetime.date(2026, 6, 15)
    assert ("   🔗 " + _URL) in _day_digest([MON, online], day).split("\n")
    assert ("      🔗 " + _URL) in _week_digest([MON, online], day).split("\n")
    lines = _day_lines([MON, online], day)
    assert len(lines) == 2 and lines[1].endswith(_URL) and "\n" in lines[1]   # 2 buổi -> 2 phần tử, link bên trong
    assert "🔗" not in _day_digest([MON, MON2], day)                           # không buổi online -> không link

def test_ics_and_gcal_meet_link():
    """ICS + Google Calendar: buổi online có link đầy đủ trong mô tả; buổi tại phòng mang mã -> KHÔNG."""
    from fapc.core.schedule import build_ics
    from fapc.app.gcal import _events
    online = dict(_sess("06/15/2026", "(09:10 - 10:40)", "EXE101", online="true"), meetURL=_CODE)
    inperson = dict(_sess("06/16/2026", "(09:10 - 10:40)", "CES202"), meetURL="zzz-yyyy-xxx")
    ics = build_ics([online, inperson])[0]
    assert "meet.google.com/abc-defg-hij" in ics and "zzz-yyyy-xxx" not in ics
    evs = {e["summary"].split()[0]: e for e in _events([online, inperson], "he190000")}
    assert evs["EXE101"]["description"].endswith(_URL)
    assert "meet.google.com" not in evs["CES202"]["description"]

def test_discord_webhook_never_pings():
    """REVIEW: nội dung webhook đến từ FAP — '@everyone' trong dữ liệu server không được ping cả server."""
    import fapc.app.notify as N
    sent, orig_post, orig_url = [], N._post_retry, N.config.DISCORD_WEBHOOK_URL
    N._post_retry = lambda url, payload: (sent.append(payload), type("R", (), {"status_code": 204})())[1]
    N.config.DISCORD_WEBHOOK_URL = "https://discord.invalid/webhook"
    try:
        assert N._discord("tin @everyone") is True
        assert sent and all(p.get("allowed_mentions") == {"parse": []} for p in sent)
    finally:
        N._post_retry, N.config.DISCORD_WEBHOOK_URL = orig_post, orig_url

def test_byweek_line_online_aware():
    """TKB-theo-tuần trước đây KHÔNG BAO GIỜ hiện 'Online'. Nay online -> '💻 Online' + link; thiếu cờ -> như cũ."""
    from fapc.app.dashboard import _byweek_line
    r = {"subjectCode": "EXE101", "roomNo": "BE-304", "slot": "2", "isOnline": "true", "meetURL": _CODE}
    out = _byweek_line(r)
    assert "💻 Online" in out and "📍" not in out and out.endswith(_URL)
    legacy = {"subjectCode": "IAP301", "roomNo": "BE-304", "slot": "1"}
    assert _byweek_line(legacy) == "   🕐 slot 1  IAP301  📍 BE-304"            # shape cũ: y hệt trước đây

# ---- feat: 4 trường API chưa dùng (attendanceStatus · studentStatus · contents · start/endDate) ----
# Mã trạng thái lấy ĐÚNG theo app chính thức (bundle): getAttendanceStatus 'P' có mặt / 'A' vắng / còn lại
# chưa diễn ra; getStatusConfig '0' đang xử lý / '1' chấp nhận / còn lại từ chối.

def test_session_status_codes_from_official_app():
    from fapc.core.attendance import session_status, att_tail
    S = lambda v: {"attendanceStatus": v}
    assert session_status(S("P")) == "present" and session_status(S("p")) == "present"
    assert session_status(S("A")) == "absent" and session_status(S(" a ")) == "absent"
    assert session_status(S("Present")) == "present" and session_status(S("Absent")) == "absent"
    for v in ("N", "", None, "Future", "Late", "X"):                # chưa diễn ra / mã lạ -> KHÔNG đoán
        assert session_status(S(v)) is None, v
    assert session_status({}) is None and session_status(None) is None
    assert att_tail(S("P")) == "  ✅" and att_tail(S("A")) == "  ❌" and att_tail(S("N")) == ""

def test_absences_and_recorded_by_subject():
    from fapc.core.attendance import absences_by_subject, recorded_by_subject, absence_line
    ss = [dict(_sess("06/19/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A"),
          dict(_sess("06/12/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A"),
          dict(_sess("06/05/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="P"),
          dict(_sess("06/26/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="N"),
          dict(_sess("06/08/2026", "(07:30 - 09:00)", "HOD402"), attendanceStatus="N"),   # chưa buổi nào ghi
          dict(_sess("", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A"),              # thiếu ngày -> bỏ
          _sess("06/09/2026", "(07:30 - 09:00)", "CES202")]                                # KHÔNG có field
    ab = absences_by_subject(ss)
    assert ab == {"IAP301": [datetime.date(2026, 6, 12), datetime.date(2026, 6, 19)]}      # tăng dần
    rec = recorded_by_subject(ss)
    assert rec["IAP301"] == 4 and rec["HOD402"] == 0                                        # P+A (kể cả buổi thiếu ngày)
    assert "CES202" not in rec                    # FAIL-SAFE: thiếu field != "0 buổi" (không được giấu cảnh báo)
    assert absence_line(ab["IAP301"]).endswith("12/06, 19/06") and "2" in absence_line(ab["IAP301"])
    assert absence_line([]) == "" and absence_line(None) == ""

def test_phase_and_att_state():
    from fapc.core.attendance import phase, att_state
    today = datetime.date(2026, 9, 25)
    r = lambda s, e: {"startDate": s, "endDate": e}
    assert phase(r("2026-10-05T00:00:00", "2026-12-20T00:00:00"), today) == "not_started"
    assert phase(r("2026-09-07T00:00:00", "2026-12-20T00:00:00"), today) == "ongoing"
    assert phase(r("2026-05-11T00:00:00", "2026-08-30T00:00:00"), today) == "ended"
    assert phase({}, today) is None and phase(r("2026-09-07T00:00:00", ""), None) is None
    assert "05/10" in att_state(r("2026-10-05T00:00:00", "2026-12-20T00:00:00"), today)
    assert att_state(r("2026-05-11T00:00:00", "2026-08-30T00:00:00"), today) in ("✔ đã kết thúc", "✔ ended")
    left = att_state(r("2026-09-07T00:00:00", "2026-10-05T00:00:00"), today)
    assert "10" in left                                                          # còn 10 ngày
    assert att_state(r("2026-09-07T00:00:00", "2026-12-20T00:00:00"), today, recorded=0) in (
        "chưa điểm danh buổi nào", "no session recorded yet")
    assert att_state({}, today) == ""

def test_at_risk_backward_compatible_and_new_guards():
    """_at_risk KHÔNG truyền tham số mới = y hệt cũ (0% thật vẫn là nguy cơ). today/recorded chỉ BỚT báo nhầm."""
    from fapc.core.attendance import _at_risk
    assert _at_risk({"attendance": "0"}) is True and _at_risk({"attendance": "60"}) is True
    assert _at_risk({"attendance": ""}) is False and _at_risk({"attendance": "100"}) is False
    today = datetime.date(2026, 9, 25)
    future = {"attendance": "0", "startDate": "2026-10-05T00:00:00", "endDate": "2026-12-20T00:00:00"}
    ongoing = {"attendance": "60", "startDate": "2026-09-07T00:00:00", "endDate": "2026-12-20T00:00:00"}
    assert _at_risk(future, today) is False                 # chưa bắt đầu: 0% đầu kỳ KHÔNG phải nguy cơ
    assert _at_risk(future) is True                         # không truyền today -> hành vi cũ
    assert _at_risk(ongoing, today) is True                 # đang học 60% -> nguy cơ thật
    assert _at_risk(ongoing, today, recorded=0) is False    # chưa buổi nào điểm danh -> chưa có gì để xét
    assert _at_risk(ongoing, today, recorded=None) is True  # KHÔNG biết (thiếu dữ liệu) -> KHÔNG được giấu
    assert _at_risk(ongoing, today, recorded=3) is True

def test_attendance_lines_render():
    from fapc.core.attendance import attendance_lines
    today = datetime.date(2026, 9, 25)
    rows = [{"subjectCode": "NEW101", "attendance": "0", "numberOfTakenAttendances": 0, "numberOfAttendances": 0,
             "startDate": "2026-10-05T00:00:00", "endDate": "2026-12-20T00:00:00"},
            {"subjectCode": "IAP301", "attendance": "60", "numberOfTakenAttendances": 3, "numberOfAttendances": 5,
             "startDate": "2026-09-07T00:00:00", "endDate": "2026-12-20T00:00:00"},
            {"subjectCode": "OLD201", "attendance": "100", "numberOfTakenAttendances": 9, "numberOfAttendances": 9,
             "startDate": "2026-05-11T00:00:00", "endDate": "2026-08-30T00:00:00"}]
    ss = [dict(_sess("09/14/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A"),
          dict(_sess("09/21/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="P")]
    out = attendance_lines(rows, today, ss, label=lambda c: c)
    txt = "\n".join(out)
    new = next(l for l in out if "NEW101" in l)
    assert "%" not in new and "⚠️" not in new and "05/10" in new     # chưa bắt đầu: KHÔNG in 0%, KHÔNG báo nhầm
    iap = out.index(next(l for l in out if "IAP301" in l))
    assert "60%" in out[iap] and "⚠️" in out[iap] and "(3/5)" in out[iap]
    assert "14/09" in out[iap + 1]                                     # dòng ngày vắng NGAY dưới môn
    assert ("✔ đã kết thúc" in txt) or ("✔ ended" in txt)
    # FAIL-SAFE: lịch KHÔNG có field attendanceStatus -> vẫn cảnh báo 60% như cũ
    plain = attendance_lines(rows[1:2], today, [_sess("09/14/2026", "(07:30 - 09:00)", "IAP301")], label=lambda c: c)
    assert "⚠️" in plain[0]
    assert attendance_lines(rows[1:2], None, None, label=lambda c: c) == ["• IAP301 — 60% ⚠️  (3/5)"]   # y hệt cũ

def test_botcore_attendance_absences_and_no_false_banrisk():
    """End-to-end qua bot_core (stub mạng): /attendance có ngày vắng; môn CHƯA bắt đầu không vào /banrisk,
    /status; và KHÔNG gọi mạng thật (tripwire)."""
    import fapc.app.bot_core as B
    saved = (B.creds, B.current_semester, B.fetch_att, B.fetch_sessions, B._vn_now, B.fetch_marks)
    try:
        B.creds = lambda: ("t", "FPTU", "HE1")
        B.current_semester = lambda *a, **k: "Fall2026"
        B._vn_now = lambda: datetime.datetime(2026, 9, 25, 8, 0)
        B.fetch_marks = lambda *a, **k: []
        B.fetch_att = lambda *a, **k: [
            {"subjectCode": "NEW101", "attendance": "0", "startDate": "2026-10-05T00:00:00", "endDate": "2026-12-20T00:00:00"},
            {"subjectCode": "IAP301", "attendance": "60", "startDate": "2026-09-07T00:00:00", "endDate": "2026-12-20T00:00:00"}]
        B.fetch_sessions = lambda *a, **k: [dict(_sess("09/14/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A")]
        att = B.handle("attendance")
        assert "14/09" in att and "NEW101" in att
        ban = B.handle("banrisk")
        assert "IAP301" in ban and "NEW101" not in ban                   # không báo nhầm môn chưa bắt đầu
        st = B.handle("status")
        assert "IAP301" in st and "NEW101" not in st.split("⚠️")[-1]
        B.fetch_sessions = lambda *a, **k: (_ for _ in ()).throw(SystemExit("token hết hạn"))
        assert "60%" in B.handle("attendance")        # phần PHỤ hỏng (kể cả SystemExit) -> màn chính vẫn hiện
    finally:
        B.creds, B.current_semester, B.fetch_att, B.fetch_sessions, B._vn_now, B.fetch_marks = saved

def test_day_digest_attendance_marks():
    past_p = dict(MON, attendanceStatus="P")
    past_a = dict(MON2, attendanceStatus="A")
    msg = _day_digest([past_p, past_a], datetime.date(2026, 6, 15))
    lines = msg.split("\n")
    assert any("EXE101" in l and l.endswith("✅") for l in lines)
    assert any("HOD402" in l and l.endswith("❌") for l in lines)
    assert "✅" not in _day_digest([dict(MON, attendanceStatus="N")], datetime.date(2026, 6, 15))
    online = dict(_sess("06/15/2026", "(13:00 - 15:00)", "EXE101", online="true"), meetURL=_CODE, attendanceStatus="P")
    lines = _day_lines([past_p, online], datetime.date(2026, 6, 15))
    assert len(lines) == 2 and "✅\n" in lines[1] and lines[1].endswith(_URL)   # dấu ✅ rồi mới tới link, vẫn 1 phần tử/buổi

def test_application_status_badges():
    """Theo getStatusConfig của myFAP 2.0.5: 0 xử lý · 1 chấp nhận · 2 HỦY · 3 chờ thanh toán · khác 'Khác'.
    (2.0.4 cho mọi mã ≠0/1 là 'từ chối' -> '2' từng bị đọc nhầm thành từ chối. KHÔNG được quay lại.)"""
    import fapc.core.extras as E
    from fapc.core.extras import app_status, _app_tally
    assert app_status({"studentStatus": "0"}).startswith("⏳")
    assert app_status({"studentStatus": "1"}).startswith("✅")
    two = app_status({"studentStatus": "2"})
    assert two.startswith("🚫") and ("hủy" in two.lower() or "cancel" in two.lower())
    assert "từ chối" not in two and "reject" not in two.lower()            # đơn bị HỦY không được báo là TỪ CHỐI
    assert app_status({"studentStatus": "3"}).startswith("💳")              # mới ở 2.0.5: chờ thanh toán
    assert app_status({"studentStatus": 0}).startswith("⏳")                # int 0 không được rơi mất
    other = app_status({"studentStatus": "7"})
    assert other.startswith("❔") and "7" in other and ("Khác" in other or "Other" in other)
    assert app_status({}) == "" and app_status({"studentStatus": ""}) == ""
    assert _app_tally([{"studentStatus": "2"}, {"studentStatus": "1"}, {"studentStatus": "2"},
                       {"studentStatus": "3"}, {}]) == "✅1 🚫2 💳1"
    orig = E.fetch_applications
    try:
        E.fetch_applications = lambda *a, **k: [
            {"name": "Đơn A", "createDate": "16/09/2023", "studentStatus": "1", "processNote": "OK"},
            {"name": "Đơn B", "createDate": "05/03/2026", "studentStatus": "2", "processNote": ""}]
        txt = E.applications_text("t", "FPTU", "HE1")
        assert "✅1 🚫1" in txt.split("\n")[0]
        b = txt.index("Đơn B")
        assert txt.index("🚫", b) < txt.index("Đơn A")                    # huy hiệu nằm ngay dưới đúng lá đơn
    finally:
        E.fetch_applications = orig

# ---- B4a: cảnh báo ĐƠN TỪ đổi trạng thái (app_changes thuần + mốc applications_state.json) ----
def _appl(aid, code, name="Đơn X", **kw):
    r = {"w_APP_ID": aid, "name": name, "createDate": "16/09/2025", "studentStatus": code, "processNote": ""}
    r.update(kw)
    return r

def test_app_changes_baseline_transition_new_and_order():
    from fapc.core.extras import app_changes, app_changes_text
    rows = [_appl("101", "0", "Đơn A"), _appl("102", "0", "Đơn B"), _appl("103", "1", "Đơn C")]
    st, ch = app_changes(None, rows)                                   # lần đầu: ghi mốc IM LẶNG
    assert st == {"101": "0", "102": "0", "103": "1"} and ch == []
    st2, ch2 = app_changes(st, rows)                                   # không đổi gì -> không báo
    assert st2 == st and ch2 == []
    rows3 = [_appl("101", "1", "Đơn A"), _appl("102", "3", "Đơn B", processNote="Nộp 50k"), _appl("103", "1", "Đơn C"),
             _appl("104", "0", "Đơn D")]
    st3, ch3 = app_changes(st2, rows3)
    assert st3 == {"101": "1", "102": "3", "103": "1", "104": "0"}
    assert [c["id"] for c in ch3] == ["102", "101", "104"]            # → 3 (thanh toán) trước, → 1 sau, rồi đơn mới
    assert ch3[0]["old"] == "0" and ch3[0]["new"] == "3" and ch3[2]["old"] is None
    txt = app_changes_text(ch3)
    lines = txt.split("\n")
    pay = next(l for l in lines if "Đơn B" in l)
    assert pay.startswith("‼️") and "⏳" in pay and "→ 💳" in pay           # old→new badge, nổi bật
    assert "📄 Đơn B (16/09/2025) · ⏳ Đang xử lý → 💳 Đang chờ thanh toán" in pay or "Pending payment" in pay
    assert "myFAP" in txt and "Nộp 50k" in txt                          # dòng hành động + phản hồi phòng ban
    assert next(l for l in lines if "Đơn A" in l).startswith("🎉")
    new = next(l for l in lines if "Đơn D" in l)
    assert "🆕" in new and "→" not in new and "⏳" in new                # đơn MỚI: trạng thái hiện tại
    assert app_changes_text([]) == ""

def test_app_changes_codes_ids_and_edge_cases():
    from fapc.core.extras import app_changes, app_changes_text
    prev = {"101": "3", "102": "0"}
    # int vs str cùng mã -> KHÔNG báo; mốc lưu int cũng so khớp được
    assert app_changes(prev, [_appl("101", 3), _appl("102", "0")])[1] == []
    assert app_changes({"101": 3}, [_appl("101", "3")])[1] == []
    # đơn biến mất -> bỏ khỏi mốc, KHÔNG báo
    st, ch = app_changes(prev, [_appl("101", "3")])
    assert st == {"101": "3"} and ch == []
    # danh sách rỗng khi mốc đang có đơn -> trục trặc tạm thời, GIỮ mốc
    assert app_changes(prev, []) == (prev, [])
    # server tạm mất trạng thái -> giữ mã cũ, không báo nhầm
    st, ch = app_changes(prev, [_appl("101", ""), _appl("102", None)])
    assert st == prev and ch == []
    # mã lạ -> nhãn 'Khác (mã N)' của app 2.0.5, vẫn báo
    st, ch = app_changes(prev, [_appl("101", "3"), _appl("102", "7")])
    assert len(ch) == 1 and ch[0]["new"] == "7"
    t7 = app_changes_text(ch)
    assert "❔" in t7 and "7" in t7 and not t7.split("\n")[2].startswith(("‼️", "🎉"))
    # khoá: 'w_app_id' chữ thường (app 2.0.5) cũng nhận; đơn thiếu mã -> không theo dõi
    lower = {"w_app_id": "105", "name": "Đơn E", "studentStatus": "0"}
    st, ch = app_changes({}, [lower, {"name": "không mã", "studentStatus": "0"}])
    assert st == {"105": "0"} and [c["id"] for c in ch] == ["105"]
    # lần đầu với 0 đơn (lấy THÀNH CÔNG) -> mốc rỗng hợp lệ
    assert app_changes(None, []) == ({}, [])

def test_app_state_corrupt_quarantine_and_roundtrip():
    import tempfile, fapc.app.notify as N
    saved = N._APP_STATE
    try:
        d = tempfile.mkdtemp()
        N._APP_STATE = os.path.join(d, "applications_state.json")
        assert N._load_app_state() is None                              # chưa có file -> chưa ghi mốc
        N._save_app_state({"101": "3"})
        assert N._load_app_state() == {"101": "3"}
        assert not [f for f in os.listdir(d) if f.endswith(".tmp")]     # tmp đã được os.replace
        for junk in ("{ broken json !!!", "[1, 2]"):                     # JSON hỏng / sai kiểu -> cô lập
            with open(N._APP_STATE, "w", encoding="utf-8") as f:
                f.write(junk)
            res = []
            out = _cap(lambda: res.append(N._load_app_state()))
            assert res == [None] and ("hỏng" in out or "corrupt" in out)   # None -> ghi mốc lại, có cảnh báo
            assert os.path.exists(N._APP_STATE + ".corrupt") and not os.path.exists(N._APP_STATE)
            os.remove(N._APP_STATE + ".corrupt")
    finally:
        N._APP_STATE = saved

def test_push_application_changes_flow():
    import tempfile, fapc.app.notify as N, fapc.core.extras as E
    from fapc.core import api as A
    saved = (N._APP_STATE, N.push, E.fetch_applications_checked, A.creds)
    try:
        N._APP_STATE = os.path.join(tempfile.mkdtemp(), "applications_state.json")
        sent = []
        N.push = lambda text: (sent.append(text), ["Telegram"])[1]
        A.creds = lambda: ("t", "FPTU", "HE000000")
        E.fetch_applications_checked = lambda *a, **k: None            # lấy lỗi -> bỏ lượt, KHÔNG ghi mốc
        _cap(N.push_application_changes)
        assert not os.path.exists(N._APP_STATE) and sent == []
        E.fetch_applications_checked = lambda *a, **k: [_appl("101", "0", "Đơn A")]
        _cap(N.push_application_changes)                               # lần đầu: ghi mốc, KHÔNG đẩy
        assert N._load_app_state() == {"101": "0"} and sent == []
        _cap(N.push_application_changes)                               # không đổi -> không đẩy
        assert sent == []
        E.fetch_applications_checked = lambda *a, **k: [_appl("101", "3", "Đơn A")]
        _cap(N.push_application_changes)
        assert len(sent) == 1 and "💳" in sent[0] and "Đơn A" in sent[0]
        assert N._load_app_state() == {"101": "3"}
        _cap(N.push_application_changes)                               # đã báo rồi -> không báo lại
        assert len(sent) == 1
    finally:
        N._APP_STATE, N.push, E.fetch_applications_checked, A.creds = saved

def test_notify_notifications_also_checks_applications_isolated():
    """`fap notify notifications` = thông báo MỚI + đơn từ đổi trạng thái (cùng nhịp, không cần job mới).
    Phần này hỏng KHÔNG làm mất phần kia; lỗi vẫn ném lại để cron thấy exit ≠ 0."""
    import fapc.app.notify as N
    saved = (N.push_new_notifications, N.push_application_changes)
    ran = []
    try:
        def _boom():
            ran.append("notif"); raise SystemExit("⚠️ Token FAP có thể đã hết hạn")
        N.push_new_notifications = _boom
        N.push_application_changes = lambda: ran.append("apps")
        try:
            _cap(lambda: N.run("notifications")); raised = False
        except SystemExit:
            raised = True
        assert raised and ran == ["notif", "apps"]
        ran.clear()
        N.push_new_notifications = lambda: ran.append("notif")
        _cap(lambda: N.run("notifications"))
        assert ran == ["notif", "apps"]
    finally:
        N.push_new_notifications, N.push_application_changes = saved

# ---- B4a: khối "Việc cần làm · To-do" (CheckOpenFeedBack · đơn '3' chờ thanh toán) ----
def _fake_call(table, log=None):
    """call() giả theo endpoint: giá trị là (http, data) hoặc Exception để ném. Ghi lại (endpoint, params)."""
    def _c(endpoint, params, *a, **k):
        if log is not None:
            log.append((endpoint, dict(params)))
        v = table.get(endpoint, (200, {"code": "200", "data": []}))
        if isinstance(v, BaseException):
            raise v
        return v
    return _c

def test_todo_items_and_block_pure():
    from fapc.core.extras import todo_items, todo_block, _feedback_open
    for v, want in ((True, True), ("true", True), (" TRUE ", True), (False, False), ("false", False),
                    ("", False), (None, None), ([], None), (1, None)):
        assert _feedback_open(v) is want, (v, want)
    pay = [{"w_APP_ID": "1", "name": "Đơn P", "createDate": "02/10/2026", "studentStatus": "3"},
           {"w_APP_ID": "2", "name": "Đơn Q", "studentStatus": 3},                 # int 3 cũng là chờ thanh toán
           {"w_APP_ID": "3", "name": "Đơn R", "studentStatus": "1"}]
    items = todo_items("true", pay)
    assert len(items) == 3 and items[0].startswith("📝") and "myFAP" in items[0]
    assert "Đơn P (02/10/2026)" in items[1] and items[1].startswith("💳") and "Đơn Q" in items[2]
    assert all("Đơn R" not in i for i in items)
    assert todo_items(False, []) == [] and todo_items(None, None) == []
    full = todo_block("true", pay)
    assert full.startswith("📌") and "3" in full.split("\n")[0] and ("chỉ ĐỌC" in full or "read-only" in full)
    none = todo_block(False, [])
    assert ("không có việc gì" in none or "nothing to do" in none) and "\n" not in none   # 1 dòng ngắn
    unk = todo_block(None, None, "⚠️ Token FAP có thể đã hết hạn")
    assert "không có việc" not in unk and "nothing to do" not in unk                # KHÔNG nói dối "không có việc"
    assert ("chưa kiểm tra được" in unk or "couldn't check" in unk) and "hết hạn" in unk
    part = todo_block(None, pay[:1])                                                # có việc + 1 nguồn không biết
    assert "💳" in part and ("Chưa kiểm tra được: feedback" in part or "Couldn't check: feedback" in part)
    part2 = todo_block(False, None)                                                 # không việc + đơn từ không biết
    assert ("không có việc gì" in part2 or "nothing to do" in part2) and "❔" in part2

def test_todo_fetch_isolates_failures_and_stays_read_only():
    import fapc.core.extras as E
    saved = E.call
    log = []
    try:
        E.call = _fake_call({
            "CheckOpenFeedBack": (200, {"code": "201", "message": "Token invalid", "data": None}),   # -> SystemExit
            "GetApplication": (200, {"code": "200", "data": [{"w_APP_ID": "9", "name": "Đơn P", "studentStatus": "3"}]}),
        }, log)
        fb, apps, err = E.todo_fetch("test-key", "FPTU", "HE000000")
        assert fb is None and apps and apps[0]["name"] == "Đơn P"         # 1 nguồn hỏng KHÔNG kéo sập nguồn kia
        assert err and ("hết hạn" in err or "expired" in err)
        assert [e for e, _ in log] == ["CheckOpenFeedBack", "GetApplication"]          # đúng 2 GET, KHÔNG endpoint ghi
        assert all(p == {"campusCode": "FPTU", "Authen": "test-key", "rollNumber": "HE000000"} for _, p in log)
        E.call = _fake_call({"CheckOpenFeedBack": (None, "Lỗi mạng (ConnectionError) khi gọi CheckOpenFeedBack"),
                             "GetApplication": RuntimeError("boom")})
        fb, apps, err = E.todo_fetch("test-key", "FPTU", "HE000000")
        assert fb is None and apps is None and err == "boom"              # mạng hỏng = không biết, KHÔNG phải []
        txt = E.todo_text("test-key", "FPTU", "HE000000")
        assert "không có việc" not in txt and "nothing to do" not in txt
        E.call = _fake_call({"CheckOpenFeedBack": (200, {"code": "200", "data": "true"})})
        assert "📝" in E.todo_text("test-key", "FPTU", "HE000000")
    finally:
        E.call = saved

def test_botcore_todo_command_menu_and_help():
    import fapc.app.bot_core as B, fapc.core.extras as E
    assert "todo" in B.COMMANDS and ("todo", B.menu_commands()[B.COMMANDS.index("todo")][1]) in B.menu_commands()
    overview = next(items for title, items in B.command_groups() if title in ("Tổng quan", "Overview"))
    assert ("todo", "📌") in [(n, e) for n, e, _ in overview]
    assert "📌 /todo" in B.help_text()
    saved = (B.creds, B.current_semester, E.call)
    try:
        B.creds = lambda: ("test-key", "FPTU", "HE000000")
        B.current_semester = lambda *a, **k: "Fall2026"
        E.call = _fake_call({"CheckOpenFeedBack": (200, {"code": "200", "data": True})})
        out = B.handle("/todo")
        assert "📝" in out and "📌" in out
    finally:
        B.creds, B.current_semester, E.call = saved

def test_notify_today_appends_todo_only_when_items():
    import fapc.app.notify as N, fapc.app.bot_core as B, fapc.core.extras as E
    from fapc.core import api as A
    saved = (N.push, B.creds, B.current_semester, B.fetch_sessions, B._vn_now, A.creds, E.call)
    try:
        sent = []
        N.push = lambda text: (sent.append(text), ["Telegram"])[1]
        B.creds = A.creds = lambda: ("test-key", "FPTU", "HE000000")
        B.current_semester = lambda *a, **k: "Summer2026"
        B.fetch_sessions = lambda *a, **k: [MON]
        B._vn_now = lambda: datetime.datetime(2026, 6, 15, 8, 0)
        E.call = _fake_call({"CheckOpenFeedBack": (200, {"code": "200", "data": True})})
        _cap(lambda: N.run("today"))
        assert "EXE101" in sent[-1] and ("Việc cần làm" in sent[-1] or "To-do" in sent[-1])
        assert sent[-1].index("EXE101") < sent[-1].index("📌")                # lịch trước, to-do gắn SAU
        E.call = _fake_call({"CheckOpenFeedBack": (200, {"code": "200", "data": False})})
        _cap(lambda: N.run("today"))
        assert "EXE101" in sent[-1] and "📌" not in sent[-1]                 # không có việc -> KHÔNG gắn gì
        E.call = _fake_call({"CheckOpenFeedBack": RuntimeError("x"), "GetApplication": (None, "Lỗi mạng")})
        _cap(lambda: N.run("today"))
        assert "EXE101" in sent[-1] and "📌" not in sent[-1]                 # lỗi -> digest lịch vẫn nguyên vẹn
        _cap(lambda: N.run("tomorrow"))
        assert "📌" not in sent[-1]                                          # chỉ digest HÔM NAY mới gắn
    finally:
        N.push, B.creds, B.current_semester, B.fetch_sessions, B._vn_now, A.creds, E.call = saved

def test_notification_preview_and_full_text():
    import fapc.core.extras as E
    from fapc.core.extras import _notif_body, _notif_line
    body = "Kính gửi SV,\n\n\n  Lịch thi   đã thay đổi.\n<b>Xem</b> &amp; phản hồi."
    assert _notif_body({"contents": body}) == "Kính gửi SV,\n\nLịch thi đã thay đổi.\nXem & phản hồi."
    long = {"id": 5, "title": "T", "contents": "x" * 500}
    ln = _notif_line(long)
    assert ln.startswith("#5 · T") and "💬" in ln and ln.endswith("…") and len(ln.split("💬 ")[1]) <= E._NOTIF_PREVIEW + 1
    assert "💬" not in _notif_line({"title": "Chỉ tiêu đề", "contents": "Chỉ tiêu đề"})   # không lặp tiêu đề
    assert _notif_line({"title": "Không id"}).startswith("• Không id")                  # thiếu id -> không số
    orig = E.fetch_notifications
    try:
        E.fetch_notifications = lambda *a, **k: [
            {"id": 101, "title": "Học phí kỳ Fall", "entryDate": "2026-06-01", "contents": "Đóng học phí trước 10/06."},
            {"id": 102, "title": "Lịch thi", "entryDate": "2026-06-09", "contents": "Thi PE ngày 20/06.\nPhòng BE-101."}]
        lst = E.notifications_text("t", "FPTU", "HE1")
        assert lst.index("#102 · Lịch thi") < lst.index("#101 · Học phí") and "💬" in lst   # số = id, mới nhất trước
        assert "\n1. " not in lst and "\n2. " not in lst            # KHÔNG dùng cú pháp danh sách Markdown (Discord đánh số lại)
        assert "/notifications" in lst.split("\n")[-1]             # gợi ý có '/' như /help
        full = E.notifications_text("t", "FPTU", "HE1", arg="101")
        assert "#101" in full and "Đóng học phí trước 10/06." in full
        assert "Phòng BE-101." in E.notifications_text("t", "FPTU", "HE1", arg="#102")   # nhận cả '#', giữ xuống dòng
        oor = E.notifications_text("t", "FPTU", "HE1", arg="9")
        assert "#9" in oor and "💬" not in oor
        flt = E.notifications_text("t", "FPTU", "HE1", arg="học phí")
        assert "#101 · Học phí" in flt and "Lịch thi" not in flt   # lọc vẫn giữ ĐÚNG số #id
        assert "PE" in E.notifications_text("t", "FPTU", "HE1", arg="pe")     # khớp cả trong NỘI DUNG
        E.notifications_text("t", "FPTU", "HE1", arg="²")          # REVIEW: '²'.isdigit() -> int() nổ; nay không nổ
        none = E.notifications_text("t", "FPTU", "HE1", arg="zzz")
        assert "zzz" in none and "💬" not in none
    finally:
        E.fetch_notifications = orig

def test_notif_body_keeps_plain_text_angle_brackets():
    """REVIEW: contents là TEXT THUẦN — '<MSSV>', 'điểm < 5', '->', '<https://…>' KHÔNG được bị coi là thẻ HTML
    và xoá mất (trước đây còn nuốt cả nhiều dòng). Thẻ HTML thật vẫn được bóc."""
    from fapc.core.extras import _notif_body
    for txt in ("Nộp file theo mẫu <MSSV>_<HoTen>.pdf", "Link: <https://forms.gle/abc>", "Diem < 5 va > 3"):
        assert _notif_body({"contents": txt}) == txt, txt
    multi = "SV có điểm TB < 5.0 phải học lại.\nHạn chót: 30/09.\nChi tiết: FAP -> Thông báo."
    assert _notif_body({"contents": multi}) == multi                    # không nuốt dòng giữa '<' và '->'
    assert _notif_body({"contents": "&lt;MSSV&gt;.pdf"}) == "<MSSV>.pdf"   # entity giải SAU khi bóc -> giữ lại
    assert _notif_body({"contents": "Dòng1<br>Dòng2 <b>đậm</b> <p>đoạn</p>"}) == "Dòng1\nDòng2 đậm đoạn"

def test_preview_never_cuts_a_url():
    from fapc.core.extras import _preview
    url = "https://forms.gle/" + "a" * 60
    s = "Điền khảo sát tại " + url + " trước thứ 6 nhé các bạn."
    p = _preview(s, 40)
    assert p.endswith("…") and "https" not in p                          # không để lại link CỤT bấm được
    assert _preview("ngắn", 40) == "ngắn" and _preview(url + " x", 30) == ""
    assert _preview("a " * 100, 20).endswith("…")

def test_att_state_last_day_and_singular():
    from fapc.core.attendance import att_state
    r = {"startDate": "2026-09-07T00:00:00", "endDate": "2026-09-25T00:00:00"}
    assert att_state(r, datetime.date(2026, 9, 25)) in ("hôm nay là ngày cuối", "last day today")   # không 'còn 0 ngày'
    assert att_state(r, datetime.date(2026, 9, 24)) in ("còn 1 ngày", "1 day left")                 # EN số ít

def test_not_started_overridden_when_sessions_recorded():
    """REVIEW fail-safe: lịch đã có buổi P/A cho môn thì môn ĐÃ bắt đầu — một startDate đọc sai không được
    giấu cảnh báo cấm thi thật."""
    from fapc.core.attendance import _at_risk, attendance_lines
    today = datetime.date(2026, 9, 25)
    r = {"subjectCode": "IAP301", "attendance": "60", "startDate": "2026-10-05T00:00:00", "endDate": "2026-12-20T00:00:00"}
    assert _at_risk(r, today) is False and _at_risk(r, today, recorded=0) is False   # thật sự chưa bắt đầu
    assert _at_risk(r, today, recorded=3) is True                                      # lịch nói đã học 3 buổi
    ss = [dict(_sess("09/14/2026", "(07:30 - 09:00)", "IAP301"), attendanceStatus="A")]
    assert "⚠️" in attendance_lines([r], today, ss, label=lambda c: c)[0]

def test_banrisk_skips_schedule_request_when_nothing_below_threshold():
    """REVIEW (nhẹ tay với server): lịch chỉ để BỚT cảnh báo nhầm -> không môn nào dưới ngưỡng thô thì KHÔNG
    tốn request GetActivityStudent. Có môn dưới ngưỡng thì mới lấy lịch."""
    import fapc.app.bot_core as B
    saved = (B.creds, B.current_semester, B.fetch_att, B.fetch_sessions, B._vn_now)
    calls = []
    try:
        B.creds = lambda: ("t", "FPTU", "HE1")
        B.current_semester = lambda *a, **k: "Fall2026"
        B._vn_now = lambda: datetime.datetime(2026, 9, 25, 8, 0)
        B.fetch_sessions = lambda *a, **k: (calls.append(1), [])[1]
        B.fetch_att = lambda *a, **k: [{"subjectCode": "A", "attendance": "100"}, {"subjectCode": "B", "attendance": "90"}]
        B.handle("banrisk")
        assert calls == []                                      # an toàn -> 0 request lịch
        B.fetch_att = lambda *a, **k: [{"subjectCode": "B", "attendance": "60"}]
        assert "B" in B.handle("banrisk") and calls == [1]      # có nguy cơ thô -> mới lấy lịch (1 lần)
    finally:
        B.creds, B.current_semester, B.fetch_att, B.fetch_sessions, B._vn_now = saved

# ---- B2: API v2 OPT-IN (FAP_API_VERSION=v2) — khoá GIẢ "test-key", token/roll giả, 0 mạng thật ----
_V2_KEY = "test-key"

def _env_set(saved):
    for k, v in saved.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v

@contextlib.contextmanager
def _v2_env(version="v2", key=_V2_KEY, stamp="v2"):
    """Bật v2 TẠM: env + token.json GIẢ ở thư mục tạm. stamp: 'v1'/'v2' = đóng dấu · False = token cũ KHÔNG có
    khoá api_version · None = không có file. Trả module apiv2; hết khối trả lại env/đường dẫn như cũ."""
    import tempfile, json as _json
    import fapc.core.apiv2 as V
    saved = {k: os.environ.get(k) for k in ("FAP_API_VERSION", "FAP_V2_KEY")}
    saved_tj = V.TOKEN_JSON
    tj = os.path.join(tempfile.mkdtemp(), "token.json")
    if stamp is not None:
        body = {"authenkey": "tok", "campus": "APHL", "rollnumber": "HE000000"}
        if stamp:
            body["api_version"] = stamp
        with open(tj, "w", encoding="utf-8") as f:
            _json.dump(body, f)
    try:
        os.environ["FAP_API_VERSION"] = version; os.environ["FAP_V2_KEY"] = key
        V.TOKEN_JSON = tj; V._SESSION_CACHE.clear()
        yield V
    finally:
        _env_set(saved); V.TOKEN_JSON = saved_tj; V._SESSION_CACHE.clear()

class _V2Resp:
    def __init__(self, js=None, status=200, text=""):
        self.status_code, self._js, self.text, self.headers = status, js, text, {}
    def json(self):
        if self._js is None: raise ValueError("not json")
        return self._js

def test_v2_checksum_matches_independent_hmac():
    """checksum_v2 == HMAC-SHA256 tính ĐỘC LẬP ngay trong test (không gọi lại hàm): khoá = byte UTF-8 của CHUỖI."""
    import hmac as _h, hashlib as _hl, base64 as _b
    from fapc.core.apiv2 import checksum_v2
    exp = _b.b64encode(_h.new(b"test-key", b"tok.ABC-123MyFAP1700000000", _hl.sha256).digest()).decode()
    exp = exp.replace("=", "%3d").replace(" ", "+")
    got = checksum_v2("tok.ABC-123", 1700000000, "test-key")
    assert got == exp, (got, exp)
    assert got.endswith("%3d") and "=" not in got           # SHA-256 = 32 byte -> base64 44 ký tự, đúng 1 '=' đệm
    assert checksum_v2("tok.ABC-123", "1700000000", "test-key") == got and checksum_v2("tok.ABC-123", 1700000001, "test-key") != got
    hk = "0a1b2c3d4e5f"                                      # khoá app TRÔNG như hex nhưng KHÔNG hex-decode
    raw = _b.b64encode(_h.new(hk.encode("utf-8"), b"tMyFAP1", _hl.sha256).digest()).decode().replace("=", "%3d")
    dec = _b.b64encode(_h.new(bytes.fromhex(hk), b"tMyFAP1", _hl.sha256).digest()).decode().replace("=", "%3d")
    assert checksum_v2("t", 1, hk) == raw and raw != dec

def test_v2_headers_shape_and_bearer_omission():
    from fapc.core.apiv2 import build_headers_v2, checksum_v2
    h = build_headers_v2("tok", "APHL", 1700000000, "test-key")
    assert list(h) == ["ClientCode", "CampusCode", "Authorization", "Checksum", "Content-Type"], list(h)
    assert h["ClientCode"] == "MyFAP" and h["CampusCode"] == "APHL" and h["Authorization"] == "Bearer tok"
    assert h["Checksum"] == checksum_v2("tok", 1700000000, "test-key") + ":1700000000"
    assert h["Content-Type"] == "application/json"
    h0 = build_headers_v2("", None, 5, "test-key")             # token rỗng -> KHÔNG Authorization (như app)
    assert "Authorization" not in h0 and h0["CampusCode"] == "" and h0["Checksum"].endswith(":5")
    assert "test-key" not in repr(h) + repr(h0)

def test_v2_request_urls_params_and_casing():
    from fapc.core.apiv2 import v2_request, BASE_V2
    P = lambda *extra: [("campusCode", "APHL"), ("Authen", "tok/+="), ("rollNumber", "HE000000")] + list(extra)
    url, tok = v2_request("GetApplication", P(), "HE000000", "APHL")        # 1 trong 7 endpoint giữ Authen trên query
    assert url == BASE_V2 + "/GetApplication?CampusCode=APHL&rollNumber=HE000000&Authen=tok%2F%2B%3D" and tok == "tok/+=", url
    url, _ = v2_request("GetStudentMark", P(("Semester", "Fall2026")), "HE000000", "APHL")   # KHÔNG Authen trên query
    assert url == BASE_V2 + "/GetStudentMark?CampusCode=APHL&rollNumber=HE000000&Semester=Fall2026", url
    url, _ = v2_request("getCourseAttendance", [("campusCode", "APHL"), ("rollNumber", "HE000000"), ("Semester", "Fall2026"),
                        ("ClassName", "SE1900"), ("SubjectCode", "PRF192"), ("Authen", "tok")], "HE000000", "APHL")
    assert url == (BASE_V2 + "/GetCourseAttendance?CampusCode=APHL&rollNumber=HE000000&Semester=Fall2026"
                   "&SubjectCode=PRF192&ClassName=SE1900"), url              # v2 viết HOA chữ đầu
    assert v2_request("GetWeekByDate", P(("date", "2026-10-03")))[0] == BASE_V2 + "/GetWeekByDate?date=2026-10-03"
    assert v2_request("GetSemester", [("campusCode", "APHL"), ("Authen", "tok")])[0] == BASE_V2 + "/GetSemester"
    url, _ = v2_request("GetMarkByCourse", P(("CourseId", "42"), ("SubjectCode", "PRF192")), "HE000000", "APHL")
    assert url == BASE_V2 + "/GetMarkByCourse?CampusCode=APHL&CourseId=42&rollNumber=HE000000", url   # app v2 không gửi SubjectCode
    assert v2_request("GetDiemphongtrao", P(("semester", "Fall2026")))[0].endswith("?CampusCode=APHL&rollNumber=HE000000&semester=Fall2026")
    url, _ = v2_request("GetStudentById", [("Authen", "tok")], "HE000000", "APHL")   # thiếu trong params -> roll/campus của call()
    assert url == BASE_V2 + "/GetStudentById?rollNumber=HE000000&CampusCode=APHL", url
    for bad in ("AddRate", "SubmitStudentFeedback", "UpdateTokedevices", "UpdateTokenDonor", "GetApiActive",
                "GetStudentRate", "NoSuchEndpoint"):
        assert _raises_exit(lambda b=bad: v2_request(b, P(), "HE000000", "APHL")), bad
    assert _raises_exit(lambda: v2_request("GetStudentMark", [("campusCode", "APHL")], "HE000000", "APHL"))   # thiếu token

def test_v2_table_covers_every_endpoint_fapcli_calls():
    """Mọi endpoint fap-cli gọi qua call()/call_login_retry (quét mã nguồn) + bảng extract đều có đường v2 (hoặc
    được miễn rõ ràng). Endpoint GHI/cấm KHÔNG BAO GIỜ nằm trong bảng."""
    import re, glob
    import fapc.core.apiv2 as V, fapc.core.extract as E
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    used = set(E.SIMPLE)
    for p in glob.glob(os.path.join(root, "fapc", "**", "*.py"), recursive=True):
        with open(p, encoding="utf-8") as f:
            used |= set(re.findall(r'\bcall(?:_login_retry)?\(\s*"(\w+)"', f.read()))
    known = set(V.ENDPOINTS) | V.V1_ONLY | V.V2_UNAVAILABLE
    assert len(used) > 20 and not (used - known), sorted(used - known)
    assert not (V.DENY & set(V.ENDPOINTS)) and not (V.DENY & used)
    assert all(m == "GET" for _p, m, _k in V.ENDPOINTS.values())
    assert V.ENDPOINTS["getCourseAttendance"][0] == "GetCourseAttendance" and V.is_unavailable("GetStudentRate")
    authen_q = sorted(k for k, (_p, _m, ks) in V.ENDPOINTS.items() if "Authen" in ks)
    assert authen_q == ["CheckOpenFeedBack", "CheckUpdateProfile", "GetApplication", "GetNotificationByRoll",
                        "GetSemesterMark"], authen_q          # 5/7 endpoint giữ Authen mà fap-cli gọi (2 còn lại: Donor/AddRate)

def test_v2_version_normalize_and_single_warning():
    import fapc.core.apiv2 as V
    N = V.normalize_version
    assert N(None) == ("v1", True) and N("") == ("v1", True) and N("  ") == ("v1", True)
    assert N("v1") == ("v1", True) and N(" V2 ") == ("v2", True)
    for bad in ("v3", "2", "true", "test-key"):
        assert N(bad) == ("v1", False), bad
    saved, w = {"FAP_API_VERSION": os.environ.get("FAP_API_VERSION")}, dict(V._WARNED)
    try:
        V._WARNED["bad_version"] = False
        os.environ["FAP_API_VERSION"] = "weird-VALUE-123"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert V.api_version() == "v1" and V.api_version() == "v1"
        out = err.getvalue()
        assert out.count("FAP_API_VERSION") == 2 and "v1" in out, out              # 1 cảnh báo = 1 dòng VI + 1 dòng EN
        assert "weird-VALUE-123" not in out                                         # không echo giá trị đã gõ
        os.environ["FAP_API_VERSION"] = "v2"
        assert V.api_version() == "v2"
    finally:
        _env_set(saved); V._WARNED.update(w)

def test_v2_session_version_mismatch_requires_refresh():
    """token.json đổi bằng phiên bản A mà FAP_API_VERSION = B -> SystemExit 'fap refresh', 0 request.
    Token cũ không có dấu = v1. Không có token.json -> không chặn (creds() tự báo 'chưa đăng nhập')."""
    import fapc.core.api as A
    calls = []
    orig = A.requests.get
    P = [("campusCode", "APHL"), ("Authen", "tok"), ("rollNumber", "HE000000")]
    def _msg(fn):
        try: fn()
        except SystemExit as e: return str(e)
        return None
    try:
        A.requests.get = lambda url, **k: (calls.append(url), _V2Resp({"code": "200", "data": []}))[1]
        A._CACHE.clear()
        for ver, stamp in (("v1", "v2"), ("v2", "v1"), ("v2", False)):
            with _v2_env(version=ver, stamp=stamp):
                m = _msg(lambda: A.call("GetStudentMark", P, "HE000000", "APHL"))
            assert m and "fap refresh" in m and "/login" in m and f"FAP_API_VERSION={ver}" in m, (ver, stamp, m)
        assert calls == []                                                   # lệch phiên bản -> KHÔNG request nào
        with _v2_env(version="v1", stamp=False):                             # token cũ + v1 = như trước đây
            assert A.call("GetStudentMark", P, "HE000000", "APHL")[0] == 200
            assert A.call("GetAllActiveCampus", [], "", "", checksum_value=False)[0] == 200
        with _v2_env(version="v2", stamp="v1"):                              # `fap campuses`: luôn v1, KHÔNG bị chặn
            assert A.call("GetAllActiveCampus", [], "", "", checksum_value=False)[0] == 200
        with _v2_env(version="v2", stamp=None) as V:                         # chưa có token.json -> không chặn
            assert A.call("GetStudentMark", P, "HE000000", "APHL")[0] == 200
        assert calls[-1].startswith(V.BASE_V2 + "/GetStudentMark?")
        assert all("api.fpt.edu.vn/fap/api/MyFAP/GetAllActiveCampus" in u for u in calls[1:3])
    finally:
        A.requests.get = orig; A._CACHE.clear()

def test_v2_missing_key_bilingual_message_no_request():
    import fapc.core.api as A
    n = len(_NET_ATTEMPTS)
    with _v2_env(key=""):
        try:
            A.call("GetStudentMark", [("campusCode", "APHL"), ("Authen", "tok")], "HE000000", "APHL"); assert False
        except SystemExit as e:
            m = str(e)
        assert "FAP_V2_KEY" in m and "python analysis/apk_drift.py --write-v2-key" in m, m
        assert "Trích" in m and "Extract" in m                                      # song ngữ, VI trước
        assert m.index("Trích") < m.index("Extract")
        saved = {"FAP_SEMESTER": os.environ.get("FAP_SEMESTER")}
        os.environ.pop("FAP_SEMESTER", None)
        try:                                                                         # hợp đồng: LUÔN chuỗi, KHÔNG raise
            with contextlib.redirect_stderr(io.StringIO()):
                assert isinstance(A.current_semester("tok", "APHL", "HE000000"), str)
        finally:
            _env_set(saved)
    assert len(_NET_ATTEMPTS) == n

def test_v2_call_round_trip_single_shot_and_cache_key():
    """call() với v2: đúng 1 request (không vòng ±1h kể cả lỗi checksum kiểu v1), header ký, timeout 15,
    không theo redirect; cache FAP_CACHE_MIN dùng chung nhưng KHÔNG trộn với khoá v1."""
    import hmac as _h, hashlib as _hl, base64 as _b
    import fapc.core.api as A
    calls = []
    orig = A.requests.get
    body = {"code": "201", "message": "Thông tin checksum không chính xác", "data": None}
    try:
        A.requests.get = lambda url, **k: (calls.append((url, k)), _V2Resp(body))[1]
        A._CACHE.clear()
        with _v2_env() as V:
            out = A.call_login_retry("GetSemester", [("campusCode", "APHL"), ("Authen", "tok")], "HE000000", "APHL")
            assert out[0] == 200 and len(calls) == 1, calls                   # v1 sẽ thử thêm (±1h)
            url, k = calls[0]
            assert url == V.BASE_V2 + "/GetSemester" and k["timeout"] == 15 and k["allow_redirects"] is False
            h = k["headers"]
            sig, ts = h["Checksum"].rsplit(":", 1)
            exp = _b.b64encode(_h.new(b"test-key", ("tokMyFAP" + ts).encode(), _hl.sha256).digest()).decode().replace("=", "%3d")
            assert sig == exp and h["Authorization"] == "Bearer tok" and h["CampusCode"] == "APHL"
            assert h.get("User-Agent") == A.UA["User-Agent"]
            body.update(code="200", message="ok", data=[1])
            os.environ["FAP_CACHE_MIN"] = "5"
            P = [("campusCode", "APHL"), ("Authen", "tok"), ("rollNumber", "HE000000"), ("Semester", "Fall2026")]
            r1 = A.call("GetStudentMark", P, "HE000000", "APHL"); r2 = A.call("GetStudentMark", P, "HE000000", "APHL")
            assert r1 == r2 and len(calls) == 2                                # lần 2 từ cache
            assert all(str(key).startswith("v2|") for key in A._CACHE)
    finally:
        A.requests.get = orig; A._CACHE.clear(); os.environ.pop("FAP_CACHE_MIN", None)

def test_v2_key_never_in_errors_or_logs():
    """Khoá v2 KHÔNG BAO GIỜ xuất hiện ở URL, header, giá trị trả về, thông điệp SystemExit hay stdout/stderr —
    kể cả khi exception của requests 'lắm lời' (nhúng url + header). Cộng: _redact che khoá/Bearer/Checksum."""
    import tempfile
    import fapc.core.api as A, fapc.core.auth as AU
    KEY = "test-key-DO-NOT-LEAK-9f8e"
    seen, texts = [], []
    orig_get, orig_post = A.requests.get, AU.requests.post
    P = [("campusCode", "APHL"), ("Authen", "TOKEN-XYZ-123"), ("rollNumber", "HE000000")]
    mode = {"v": "ok"}
    def fake_get(url, **k):
        seen.append(url); seen.append(repr(k.get("headers")))
        if mode["v"] == "net":
            raise A.requests.ConnectionError(f"boom {url} {k.get('headers')}")
        if mode["v"] == "html":
            return _V2Resp(None, status=500, text="<html>err</html>")
        if mode["v"] == "expired":
            return _V2Resp({"code": "401", "errorMessage": "Unauthorized", "data": None})
        return _V2Resp({"code": "200", "data": [{"x": 1}]})
    def fake_post(url, **k):
        seen.append(url); seen.append(repr(k.get("headers")))
        raise AU.requests.ConnectionError(f"boom {url} {k.get('headers')}")
    def grab(fn):
        o, e = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                texts.append(repr(fn()))
        except SystemExit as ex:
            texts.append(str(ex))
        texts.extend([o.getvalue(), e.getvalue()])
    saved_tj, saved_out = AU.TOKEN_JSON, AU.OUT
    try:
        A.requests.get, AU.requests.post = fake_get, fake_post
        AU.TOKEN_JSON = os.path.join(tempfile.mkdtemp(), "token.json"); AU.OUT = os.path.dirname(AU.TOKEN_JSON)
        with _v2_env(key=KEY) as V:
            for mode["v"] in ("ok", "net", "html", "expired"):
                A._CACHE.clear()
                grab(lambda: A.call("GetApplication", P, "HE000000", "APHL"))
                grab(lambda: A.check_auth(*A.call("GetStudentMark", P, "HE000000", "APHL")))
            grab(lambda: A.call("AddRate", P, "HE000000", "APHL"))                      # cấm
            grab(lambda: A.call("GetStudentMark", P[:1], "HE000000", "APHL"))           # thiếu token
            grab(lambda: AU._do_fap("APHL", "FE-ACCESS-TOKEN", log=print))               # đăng nhập v2 lỗi mạng
            assert "x *** y" == V.scrub(f"x {KEY} y") and V.scrub("a FE-ACCESS-TOKEN b", "FE-ACCESS-TOKEN") == "a *** b"
        with _v2_env(version="v1", key=KEY, stamp="v2"):
            grab(lambda: A.call("GetStudentMark", P, "HE000000", "APHL"))               # lệch phiên bản
        assert seen and any("Checksum" in s for s in seen)                              # đã thật sự ký
        blob = "\n".join(seen + texts)
        assert KEY not in blob, "khoá v2 lọt ra!"
        net = [x for x in texts if "Lỗi mạng" in x]
        assert net and not any("TOKEN-XYZ-123" in x or "FE-ACCESS-TOKEN" in x for x in net)   # như v1: không str(e)
        r = AU._redact({"Authorization": "Bearer t", "Checksum": "sig:1", "FAP_V2_KEY": KEY, "ok": 1})
        assert r == {"Authorization": "***REDACTED***", "Checksum": "***REDACTED***", "FAP_V2_KEY": "***REDACTED***", "ok": 1}
    finally:
        A.requests.get, AU.requests.post = orig_get, orig_post
        AU.TOKEN_JSON, AU.OUT = saved_tj, saved_out; A._CACHE.clear()

def test_v2_auth_exchange_shape_and_api_version_stamp():
    """Đăng nhập v2: POST fap-proxy …/AuthenticationByFeId, body {token: FE}, Bearer + Checksum bằng CHÍNH token FE,
    KHÔNG query; token.json đóng dấu api_version. v1 giữ đường cũ (đóng dấu 'v1'). v2 thiếu khoá -> None, 0 request."""
    import tempfile, json as _json, time as _t, hmac as _h, hashlib as _hl, base64 as _b
    import fapc.core.auth as AU
    d = tempfile.mkdtemp()
    saved = (AU.TOKEN_JSON, AU.OUT, AU.requests.post)
    seen = {}
    class _R:
        status_code = 200
        def json(s): return {"code": "200", "message": "ok", "data": {"authenKey": "FAPTOK", "rollnumber": "HE000000",
                                                                       "email": "a@b.c", "studentName": "Test"}}
    def fake_post(url, json=None, headers=None, timeout=None, allow_redirects=True, **k):
        seen.update(url=url, body=json, headers=dict(headers or {}), timeout=timeout, redirects=allow_redirects)
        return _R()
    quiet = lambda *a, **k: None
    try:
        AU.TOKEN_JSON = os.path.join(d, "token.json"); AU.OUT = d
        AU.requests.post = fake_post
        with _v2_env(stamp=None):
            fap = AU._do_fap("APHL", "FE.ACCESS.TOKEN", log=quiet)
        assert fap and fap["authenkey"] == "FAPTOK" and fap["rollnumber"] == "HE000000" and fap["api_version"] == "v2"
        with open(AU.TOKEN_JSON, encoding="utf-8") as f:
            assert _json.load(f)["api_version"] == "v2"
        assert seen["url"] == "https://fap-proxy.fpt.edu.vn/MyFAP/AuthenticationByFeId", seen["url"]   # không query
        assert seen["body"] == {"token": "FE.ACCESS.TOKEN"} and seen["timeout"] == 15 and seen["redirects"] is False
        h = seen["headers"]
        assert h["Authorization"] == "Bearer FE.ACCESS.TOKEN" and h["CampusCode"] == "APHL" and h["ClientCode"] == "MyFAP"
        sig, ts = h["Checksum"].rsplit(":", 1)
        exp = _b.b64encode(_h.new(b"test-key", ("FE.ACCESS.TOKEN" + "MyFAP" + ts).encode(), _hl.sha256).digest()).decode()
        assert sig == exp.replace("=", "%3d") and abs(int(ts) - _t.time()) < 300
        with _v2_env(version="v1", stamp=None):                         # mặc định v1: ĐƯỜNG CŨ, đóng dấu 'v1'
            fap1 = AU._do_fap("APHL", "FE.ACCESS.TOKEN", log=quiet)
        assert fap1["api_version"] == "v1" and "fap-proxy" not in seen["url"]
        assert "/fap/api/MyFAP/AuthenticationByFeId?campusCode=APHL&checksum=" in seen["url"]
        os.remove(AU.TOKEN_JSON); seen.clear(); logs = []
        with _v2_env(key="", stamp=None):                               # thiếu khoá: None (để _finish HOÀN TÁC), 0 request
            assert AU._do_fap("APHL", "FE.ACCESS.TOKEN", log=logs.append) is None
        assert not seen and not os.path.exists(AU.TOKEN_JSON) and any("FAP_V2_KEY" in l for l in logs)
    finally:
        AU.TOKEN_JSON, AU.OUT, AU.requests.post = saved

def test_extract_skips_studentrate_on_v2_only():
    import tempfile
    import fapc.core.extract as E
    names = []
    saved = (E.creds, E.current_semester, E.call, E.save, E.APIOUT, E.DB)
    saved_env = {k: os.environ.get(k) for k in ("FAP_API_VERSION", "FAP_EXTRACT_DELAY")}
    try:
        E.creds = lambda: ("tok12345678", "APHL", "HE000000")
        E.current_semester = lambda *a, **k: "Fall2026"
        E.call = lambda ep, params, roll, campus, **k: (names.append(ep), (200, {"code": "200", "data": []}))[1]
        E.save = lambda *a, **k: None
        E.APIOUT = tempfile.mkdtemp(); E.DB = os.path.join(E.APIOUT, "nope")
        os.environ["FAP_EXTRACT_DELAY"] = "0"
        for ver, expect in (("v1", True), ("v2", False)):
            names.clear(); os.environ["FAP_API_VERSION"] = ver
            out = _cap(E.main)
            assert ("GetStudentRate" in names) is expect, (ver, names)
            assert ("GetAllActiveCampus" in names) and ("GetStudentMark" in names)
            if ver == "v2":
                assert "GetStudentRate" in out and "API v2" in out, out[:300]
    finally:
        (E.creds, E.current_semester, E.call, E.save, E.APIOUT, E.DB) = saved
        _env_set(saved_env)
# ---- analysis/apk_drift.py: masker · bộ đọc bảng chuỗi HBC · rút endpoint · ghi .env ----
# apk_drift CHỈ dùng thư viện chuẩn, KHÔNG import fapc, KHÔNG gọi mạng -> an toàn nạp ở đây.
import struct as _struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis"))
import apk_drift as _ad


def _hbc_blob(strings, version=96):
    """Dựng một bundle Hermes TỐI GIẢN (ASCII, 0 function/kind/identifier/overflow) cho bộ đọc.

    Chỉ đủ để test HBC.strings — khớp đúng đường parse của apk_drift.HBC."""
    storage = b""
    entries = []
    for s in strings:
        raw = s.encode("ascii")
        off = len(storage)
        storage += raw
        assert len(raw) < 0xFF
        entries.append((_struct.pack("<I", (len(raw) << 24) | (off << 1))))  # isUTF16=0
    small_tbl = b"".join(entries)
    # header: magic(8)+version(4)+hash(20) = 32, rồi 19 u32, rồi 1 byte cờ
    hdr = _struct.pack("<Q", _ad.HBC_MAGIC) + _struct.pack("<I", version) + b"\x00" * 20
    u32s = [
        0,                 # fileLength (không kiểm)
        0,                 # globalCodeIndex
        0,                 # functionCount
        0,                 # stringKindCount
        0,                 # identifierCount
        len(strings),      # stringCount
        0,                 # overflowStringCount
        len(storage),      # stringStorageSize
        0, 0,              # bigIntCount, bigIntStorageSize (v>=87)
        0, 0,              # regExpCount, regExpStorageSize
        0, 0, 0,           # arrayBufferSize, objKeyBufferSize, objValueBufferSize (v<97)
        0, 0,              # segmentID, cjsModuleCount
        0,                 # functionSourceCount (v>=84)
        0,                 # debugInfoOffset
    ]
    hdr += b"".join(_struct.pack("<I", x) for x in u32s) + b"\x00"  # 1 byte cờ
    out = bytearray(hdr)
    def _pad(buf, n):
        while len(buf) % n:
            buf += b"\x00"
    _pad(out, 32)                 # căn 32 trước function headers (0 function -> chỉ padding)
    _pad(out, 4); out += small_tbl        # string kinds(0)+identifier(0) rỗng -> ngay small table
    _pad(out, 4)                          # overflow(0) rỗng
    _pad(out, 4); out += storage
    return bytes(out)


def test_apkdrift_masker():
    m = _ad.safe
    assert m("GetStudentMark") == "GetStudentMark"            # định danh -> giữ
    assert m("sessionApiVersion") == "sessionApiVersion"
    assert m("MyFAP/GetApiActive") == "MyFAP/GetApiActive"
    assert m("[OTA]") == "[OTA]"
    assert m("deadbeef1234cafe") == "<masked:hex>"            # hex>=12 có chữ số
    assert m("HE000000") == "<masked:roll>"                   # mã SV (không word-boundary)
    assert m("a@b.com") == "<masked:email>"
    assert m("eyJhbGciOi") == "<masked:jwt>"
    assert m("123456789") == "<masked:number>"                # dãy số dài
    assert m("Bearer abcd1234efgh") == "<masked:credential>"
    assert m("Nguyễn Văn A") == "<masked:name?>"              # tên riêng VN
    # URL: giữ scheme/host/path, GIẤU giá trị query
    assert m("https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentMark?Authen=zzz") == \
        "https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentMark?Authen=<v>"


def test_apkdrift_looks_secret():
    assert _ad._looks_secret("deadbeef1234") is True
    assert _ad._looks_secret("GetStudentMark") is False
    assert _ad._looks_secret("abcdefabcdef") is False         # hex nhưng KHÔNG có chữ số


def test_apkdrift_extract_sets_and_markers():
    strings = [
        "https://api.fpt.edu.vn/fap/api/MyFAP/GetStudentMark?campusCode=x",
        "https://api.fpt.edu.vn/fap/api/MyFAP/getCourseAttendance",
        "https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey?username=x",
        "MyFAP/GetApiActive", "MyFAP/GetStudentMark", "MyFAP/GetCourseAttendance",
        "https://fap-proxy.fpt.edu.vn", "https://api.fpt.edu.vn",
        "sessionApiVersion", "[OTA]", "v1", "v2",
    ]
    info = _ad.extract(strings)
    assert info["v1"] == {"GetStudentMark", "getCourseAttendance"}
    assert info["survey"] == {"GetRequiredSurvey"}
    assert info["v2"] == {"GetApiActive", "GetStudentMark", "GetCourseAttendance"}
    assert "https://fap-proxy.fpt.edu.vn" in info["hosts"]
    assert info["markers"]["fap_proxy"] and info["markers"]["sessionApiVersion"]
    assert info["markers"]["OTA"] and info["markers"]["v1_literal"] and info["markers"]["v2_literal"]
    # case-SENSITIVE: v1 có 'getCourseAttendance' thường, v2 có 'GetCourseAttendance' hoa -> KHÁC tập
    assert "getCourseAttendance" in info["v1"] and "getCourseAttendance" not in info["v2"]


def test_apkdrift_hbc_reader_synthetic():
    names = ["GetStudentMark", "sessionApiVersion", "MyFAP/GetApiActive", ""]
    blob = _hbc_blob(names)
    hbc = _ad.HBC(blob)
    assert hbc.version == 96
    assert hbc.strings == names


def test_apkdrift_hbc_reader_rejects():
    # magic sai
    try:
        _ad.HBC(b"\x00" * 64); assert False
    except _ad.HBCError:
        pass
    # version ngoài dải hỗ trợ
    bad = bytearray(_hbc_blob(["x"]))
    _struct.pack_into("<I", bad, 8, 200)
    try:
        _ad.HBC(bytes(bad)); assert False
    except _ad.HBCError:
        pass


def test_apkdrift_load_bundle(tmp_path=None):
    import tempfile, zipfile as _zip
    blob = _hbc_blob(["GetStudentMark"])
    d = tempfile.mkdtemp()
    raw = os.path.join(d, "index.android.bundle")
    with open(raw, "wb") as f:
        f.write(blob)
    data, src = _ad.load_bundle(raw)
    assert data == blob and src == "bundle"
    apk = os.path.join(d, "app.apk")
    with _zip.ZipFile(apk, "w") as z:
        z.writestr("assets/index.android.bundle", blob)
        z.writestr("AndroidManifest.xml", b"x")
    data2, src2 = _ad.load_bundle(apk)
    assert data2 == blob and src2.startswith("APK:")


def test_apkdrift_write_v2_key(tmp_path=None):
    import tempfile
    d = tempfile.mkdtemp()
    env = os.path.join(d, ".env")
    # append khi chưa có
    with open(env, "w", encoding="utf-8") as f:
        f.write("FAP_LANG=en\nTELEGRAM_TOKEN=keepme\n")
    _ad.write_v2_key(env, "cafe1234deadbeef")
    lines = open(env, encoding="utf-8").read().splitlines()
    assert "FAP_LANG=en" in lines and "TELEGRAM_TOKEN=keepme" in lines
    assert "FAP_V2_KEY=cafe1234deadbeef" in lines
    # thay TẠI CHỖ (không nhân đôi), giữ dòng khác
    _ad.write_v2_key(env, "beef5678feedface")
    lines = open(env, encoding="utf-8").read().splitlines()
    assert sum(1 for ln in lines if ln.startswith("FAP_V2_KEY=")) == 1
    assert "FAP_V2_KEY=beef5678feedface" in lines
    assert "FAP_LANG=en" in lines and "TELEGRAM_TOKEN=keepme" in lines


# ---- runner không cần pytest ----
def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        before = len(_NET_ATTEMPTS)
        try:
            fn()
            if len(_NET_ATTEMPTS) > before:                  # tripwire: test đã THỬ gọi mạng thật
                raise AssertionError(f"made {len(_NET_ATTEMPTS) - before} REAL network call(s): "
                                     f"{_NET_ATTEMPTS[before:][:3]}")
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
