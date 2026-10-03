#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integration_offline.py — KIỂM THỬ TÍCH HỢP OFFLINE (KHÔNG gọi mạng, KHÔNG đụng state thật).

Khác test_logic.py (unit thuần): file này MOCK 1 chokepoint mạng (api.requests.get) bằng dữ liệu
giả ĐÚNG FIELD THẬT, rồi chạy MỌI lệnh qua đường dẫn code thật — success + các đường LỖI/BIÊN:
token hết hạn, mất mạng (+ kiểm rò token), data rỗng, state hỏng, watcher 2 vòng, ICS.

Chạy (từ gốc repo):   python tests/integration_offline.py
(KHÔNG chạy chung pytest với test_logic.py — file này mock global, nên để chạy độc lập.)
"""
import os, sys, io, contextlib, tempfile, importlib
from urllib.parse import parse_qs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FAP_SEMESTER"] = "Summer2026"; os.environ["FAP_LANG"] = "vi"
# API v2 OPT-IN: ghim v1 + xoá khoá v2 TRƯỚC import fapc (đặt ở đây THẮNG .env thật). Mục [V2] tự bật bằng khoá GIẢ.
os.environ["FAP_API_VERSION"] = "v1"; os.environ["FAP_V2_KEY"] = ""

OK = {"n": 0}; FAIL = {"n": 0}
def _cap(fn):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn()
def check(label, cond, info=""):
    if cond: OK["n"] += 1
    else: FAIL["n"] += 1; print(f"  FAIL {label}  {info}")
def no_raise(label, fn):
    try: _cap(fn); check(label, True)
    except BaseException as e: check(label, False, f"{type(e).__name__}: {e}")
def raises_exit(label, fn):
    try: _cap(fn); check(label, False, "không raise")
    except SystemExit: check(label, True)
    except BaseException as e: check(label, False, f"{type(e).__name__}: {e}")

import fapc.core.api as api
SUCCESS = {
    "GetActivityStudent": [{"date": "06/23/2026", "slotTime": "(07:30 - 09:50)", "subjectCode": "IAP301", "roomNo": "BE-304", "isOnline": "false", "groupName": "G", "slot": "1"}],
    "GetStudentMark": [{"subjectCode": "EXE101", "averageMark": "0.0", "status": "Not Passed", "courseID": "1"},
                       {"subjectCode": "IAP301", "averageMark": "8.5", "status": "Passed", "courseID": "2"}],
    "GetMarkByCourse": [{"component": "Assignment", "value": "8.5", "weight": "100", "courseID": "2"}],
    "GetCourseOfSemester": [{"subjectCode": "IAP301", "courseId": "2"}, {"subjectCode": "FRS401c", "courseId": "9"}],
    "GetStudentAttendances": [{"subjectCode": "IAP301", "attendance": "100", "numberOfTakenAttendances": 5, "numberOfAttendances": 5, "groupName": "G"},
                              {"subjectCode": "CES202", "attendance": "60", "numberOfTakenAttendances": 3, "numberOfAttendances": 5, "groupName": "G"}],
    "AcademicTranscript": [{"subjectCode": "PRF192", "averageMark": "8.0", "credit": "3", "semesterName": "Fall2025"}],
    "GetScheduleExam": [{"subjectCode": "IAP301", "examDate": "06/25/2026", "examTime": "07:30", "examRoom": "BE-101"}],
    "GetNotificationByRoll": [{"id": 1, "title": "A", "entryDate": "2026-06-20T00:00:00"}, {"id": 2, "title": "B", "entryDate": "2026-06-21T00:00:00"}],
    "getCourseAttendance": [{"scheduleID": 1, "date": "2026-06-23T00:00:00", "slot": 1, "roomNo": "B", "attendanceStatus": "Present"}],
    "GetSemester": [{"semesterName": "Summer2026", "termID": "1", "campusID": "1",
                     "startDate": "2026-05-11T00:00:00", "endDate": "2026-08-30T00:00:00"},
                    {"semesterName": "Fall2026", "termID": "2", "campusID": "1",
                     "startDate": "2026-09-07T00:00:00", "endDate": "2026-12-27T00:00:00"}],
    "GetBalance": "50000", "GeFeeByRoll": [{"amount": "1000000"}], "GetTop10News": [{"title": "T"}]}
MODE = {"v": "success"}
class _R:
    def __init__(s, d, c="200"): s.status_code = 200; s._d = d; s._c = c
    def json(s): return {"message": "ok", "code": s._c, "errorMessage": None, "data": s._d}
def fake_get(url, **k):
    ep = url.split("/MyFAP/")[1].split("?")[0]
    if MODE["v"] == "expired": return type("R", (), {"status_code": 200, "json": lambda s: {"message": "Token invalid", "code": "201", "data": None}})()
    if MODE["v"] == "netdown": raise api.requests.RequestException("simulated down")
    if MODE["v"] == "empty":   return _R([] if ep != "GetBalance" else "")
    if ep == "GetActivityStudent":
        # Server trả RỖNG khi hỏi kỳ trường CHƯA xếp lịch (hay gặp khi xem kỳ sau) -> mock phải tôn
        # trọng tham số Semester, nếu không đường "kỳ chưa có lịch" của /semester không bao giờ chạy.
        q = parse_qs(url.split("?", 1)[1]) if "?" in url else {}
        if (q.get("Semester") or [""])[0] not in ("", os.environ["FAP_SEMESTER"]):
            return _R([])
    return _R(SUCCESS.get(ep, []))
api.requests.get = fake_get; api._CACHE.clear()
try: api.creds()
except SystemExit: api.creds = lambda: ("SECRETTOKEN123", "FPTU", "HE190000")
import fapc.app.notify as notify
_REAL_TELEGRAM = notify._telegram          # giữ hàm THẬT để [I] kiểm việc cắt tin dài
notify._telegram = lambda t: False; notify._discord = lambda t: False
import fapc.app.attendwatch as aw, fapc.app.gradewatch as gw
_tmp = tempfile.mkdtemp()
aw.STATE = os.path.join(_tmp, "a.json"); gw.STATE = os.path.join(_tmp, "g.json"); notify._SEEN_NOTIF = os.path.join(_tmp, "s.json")
from fapc.app.bot_core import handle, COMMANDS
import fapc.core.grades as g, fapc.core.attendance as at, fapc.core.transcript as tr, fapc.core.whatif as wi
import fapc.app.dashboard as db, fapc.core.extras as ex, fapc.core.schedule as sched

# [A] import mọi module
for m in ["config","i18n","fmt","cli","core.api","core.auth","core.schedule","core.grades","core.attendance","core.transcript","core.whatif","core.extract","core.extras","app.cli","app.notify","app.bot_core","app.dashboard","app.attendwatch","app.gradewatch","app.webui","app.telegrambot","app.discordbot","app.gcal"]:
    try: importlib.import_module(f"fapc.{m}"); check(f"import {m}", True)
    except BaseException as e: check(f"import {m}", False, str(e))
# [B] success
MODE["v"] = "success"
# Lệnh CÓ tham số: chạy cả arg HỢP LỆ lẫn arg KHÔNG tra ra — cả hai đều phải TRẢ LỜI, không raise
# (bot gửi thẳng chữ người dùng gõ vào đây, nên đường "gõ sai" cũng là đường chính thức).
ARGS = {"whatif":        [None, "8", "khong-phai-so"],
        "grades-detail": [None, "IAP301", "iap", "zzz999"],
        "semester":      [None, "weeks", "list", "Fall1999", "Fall2026 weeks"],
        "notifications": [None, "1", "999", "học phí", "zzz"]}
for c in COMMANDS:
    if c == "help": continue
    for a in ARGS.get(c, [None]):
        no_raise(f"handle/{c}" + (f" [{a}]" if a else ""), lambda c=c, a=a: handle(c, a))
for lbl, fn in [("grades.report", g.report), ("grades.detail", g.detail), ("grades.detail.raw", lambda: g.detail(raw=True)), ("att.report", at.report), ("banrisk", at.banrisk), ("transcript", tr.report), ("gpa", tr.gpa_report), ("whatif", lambda: wi.run("8")), ("status", db.status), ("week", lambda: db.week(None)), ("exams", ex.exams), ("news", ex.news), ("fees", ex.fees), ("notifications", ex.notifications), ("exams_ics", ex.exams_ics)]:
    no_raise("ok:" + lbl, fn)
# [C] token hết hạn
MODE["v"] = "expired"; api._CACHE.clear()
for lbl, fn in [("grades", g.report), ("att", at.report), ("gpa", tr.gpa_report), ("exams", ex.exams), ("fees", ex.fees), ("notif", ex.notifications)]:
    raises_exit("expired:" + lbl, fn)
MODE["v"] = "success"; api._CACHE.clear()
check("grades-detail merges GetCourseOfSemester subject (P7)", "FRS401c" in _cap(lambda: handle("grades-detail")))
check("courses roster renders (P8)", "IAP301" in _cap(lambda: handle("courses")))
# feat20: lọc 1 môn qua bot/web (arg đi trọn đường handle -> detail_text -> subjects.resolve)
one = _cap(lambda: handle("grades-detail", "iap"))
check("grades-detail lọc đúng 1 môn", "IAP301" in one and "FRS401c" not in one and "EXE101" not in one, one[:120])
unk = _cap(lambda: handle("grades-detail", "zzz999"))
check("grades-detail môn lạ -> liệt kê môn trong kỳ", "IAP301" in unk and "FRS401c" in unk and "zzz999" in unk, unk[:120])
# feat20: lịch cả kỳ — có chữ, có ghi chú trung thực, không rò 'None' vào header tuần
sem_txt = _cap(lambda: handle("semester"))
check("semester render + ghi chú week-exact", "IAP301" in sem_txt and "week-exact" in sem_txt, sem_txt[:120])
# Gợi ý "kỳ xem được" lọc theo NGÀY HIỆN TẠI -> ghim đồng hồ, nếu không test tự đỏ khi Summer2026
# kết thúc (31/08/2026) dù code không đổi gì. Ghim rồi trả lại ngay.
_saved_now = sched._vn_now
sched._vn_now = lambda: __import__("datetime").datetime(2026, 8, 20)
try:
    _sem_empty = _cap(lambda: handle("semester", "Fall2030"))   # kỳ trường chưa xếp lịch -> KHÔNG được rỗng
finally:
    sched._vn_now = _saved_now
check("semester kỳ trống -> báo rõ + gợi ý kỳ xem được",
      "🚧" in _sem_empty and "Fall2030" in _sem_empty and "Summer2026" in _sem_empty, _sem_empty[:150])
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()): db.week(None)
_wk = _buf.getvalue()
check("week header không rò 'None'", "None" not in _wk and _wk.strip() != "", _wk[:120])
MODE["v"] = "expired"; api._CACHE.clear()
check("handle expired->msg refresh", "refresh" in _cap(lambda: handle("grades")).lower())
check("handle all expired->no crash", "refresh" in _cap(lambda: handle("all")).lower())
# [D] mất mạng + không rò token
MODE["v"] = "netdown"; api._CACHE.clear()
http, data = api.call("GetStudentMark", [("Authen", "SECRETTOKEN123")], "HE1", "FPTU")
check("netdown->(None,msg)", http is None)
check("NO token leak in net error", "SECRETTOKEN123" not in str(data), repr(data))
no_raise("netdown grades graceful", g.report); no_raise("netdown status graceful", db.status)
# [E] data rỗng
MODE["v"] = "empty"; api._CACHE.clear()
for lbl, fn in [("grades", g.report), ("att", at.report), ("transcript", tr.report), ("gpa", tr.gpa_report), ("exams", ex.exams), ("notif", ex.notifications), ("whatif", lambda: wi.run(None)), ("status", db.status)]:
    no_raise("empty:" + lbl, fn)
# [F] state hỏng -> .corrupt
for mod, nm in [(gw, "g"), (aw, "a")]:
    with open(mod.STATE, "w", encoding="utf-8") as f: f.write("{ broken !!!")
    _cap(mod._load_state); check(f"{nm}watch corrupt->.corrupt", os.path.exists(mod.STATE + ".corrupt"))
# [G] watcher 2 vòng
m0 = [{"subjectCode": "X", "courseID": "1", "averageMark": "0.0"}]
_, st0, f0 = gw.compute(m0, lambda s, c: [{"component": "A", "value": ""}], {})
ev1, _, _ = gw.compute(m0, lambda s, c: [{"component": "A", "value": "9.0"}], st0)
check("gradewatch 2-cycle detects", f0 and any(e["value"] == "9.0" for e in ev1))
s0 = [{"subjectCode": "X", "groupName": "G", "numberOfTakenAttendances": 1}]
d0 = [{"scheduleID": 1, "date": "2026-06-01T00:00:00", "slot": 1, "attendanceStatus": "Present"}]
_, ast0, af0 = aw.compute(s0, lambda s, gg: d0, {})
s1 = [{"subjectCode": "X", "groupName": "G", "numberOfTakenAttendances": 2}]
d1 = d0 + [{"scheduleID": 2, "date": "2026-06-08T00:00:00", "slot": 1, "attendanceStatus": "Present"}]
aev, _, _ = aw.compute(s1, lambda s, gg: d1, ast0)
check("attendwatch 2-cycle detects", af0 and len(aev) == 1)
# [H] ICS
ics, n, sk, amb = sched.build_ics(SUCCESS["GetActivityStudent"])
check("build_ics valid", "BEGIN:VCALENDAR" in ics and n == 1)
eics, en, esk = ex.build_exam_ics(SUCCESS["GetScheduleExam"] * 2)
check("exam ics unique UID + reminder", eics.count("BEGIN:VEVENT") == 2 and "-0@fap" in eics and "-1@fap" in eics and "TRIGGER:-P1D" in eics)
# [I] tin DÀI đi qua _telegram THẬT: phải thành NHIỀU mẩu, không mẩu nào vượt trần, KHÔNG mất chữ
# (trước đây `text[:4000]` cắt cụt — /grades-detail 6 môn mất 1325 ký tự trên Telegram).
_posts = []
class _OKPost:
    status_code = 200; ok = True; text = "ok"; headers = {}
    def json(self): return {"ok": True}
def _fake_post(url, json=None, **k):
    _posts.append((json or {}).get("text", "")); return _OKPost()
_real_post, _real_sleep = notify.requests.post, notify.time.sleep
_real_tok, _real_chat = notify.config.TELEGRAM_TOKEN, notify.config.TELEGRAM_CHAT
try:
    notify.requests.post = _fake_post
    notify.time.sleep = lambda s: None                       # bỏ 0.4s nghỉ giữa 2 mẩu -> test chạy nhanh
    notify.config.TELEGRAM_TOKEN, notify.config.TELEGRAM_CHAT = "T", "C"
    long_msg = "\n".join(f"📘 dòng {i} " + "x" * 60 for i in range(200))
    sent_ok = _cap(lambda: _REAL_TELEGRAM(long_msg))
    check("telegram tin dài -> nhiều mẩu", sent_ok and len(_posts) > 1, f"{len(_posts)} mẩu")
    check("telegram mẩu nào cũng <= trần", all(len(p) <= notify.TELEGRAM_LIMIT for p in _posts))
    check("telegram KHÔNG mất chữ khi cắt", "\n".join(_posts) == long_msg)
    _posts[:] = []
    short_ok = _cap(lambda: _REAL_TELEGRAM("một dòng ngắn"))
    check("telegram tin ngắn vẫn đúng 1 tin", short_ok and _posts == ["một dòng ngắn"])
finally:
    notify.requests.post, notify.time.sleep = _real_post, _real_sleep
    notify.config.TELEGRAM_TOKEN, notify.config.TELEGRAM_CHAT = _real_tok, _real_chat

# [J] link Meet cho buổi ONLINE — đi ĐƯỜNG THẬT: GetActivityStudent (mock) -> fetch_sessions -> fill_meet
#     -> render. Shape giống dữ liệu thật: `meetURL` là MÃ TRẦN, chỉ gắn vào VÀI buổi của lớp.
import datetime
from fapc.core.schedule import fetch_sessions as _fs, build_ics as _ics
from fapc.app.notify import _day_digest as _dd
from fapc.app.reminders import reminder_text as _rt
_saved_act = SUCCESS["GetActivityStudent"]
MODE["v"] = "success"
SUCCESS["GetActivityStudent"] = [
    {"date": "06/22/2026", "slotTime": "(07:30 - 09:00)", "subjectCode": "EXE101", "roomNo": "", "isOnline": "true",
     "groupName": "G", "slot": "1", "meetURL": "abc-defg-hij"},
    {"date": "06/29/2026", "slotTime": "(07:30 - 09:00)", "subjectCode": "EXE101", "roomNo": "", "isOnline": "true",
     "groupName": "G", "slot": "1", "meetURL": ""},                      # online nhưng FAP KHÔNG gắn mã
    {"date": "06/29/2026", "slotTime": "(09:10 - 10:40)", "subjectCode": "CES202", "roomNo": "BE-305", "isOnline": "false",
     "groupName": "G", "slot": "2", "meetURL": "zzz-yyyy-xxx"},          # tại phòng nhưng CÓ mã
]
api._CACHE.clear()
try:
    _ss = _cap(lambda: _fs("SECRETTOKEN123", "FPTU", "HE190000", os.environ["FAP_SEMESTER"]))
    check("meet: fetch_sessions giữ đủ buổi", len(_ss) == 3, str(len(_ss)))
    check("meet: buổi online thiếu mã MƯỢN mã của lớp", _ss[1].get("meetURL") == "abc-defg-hij", str(_ss[1].get("meetURL")))
    _txt = _dd(_ss, datetime.date(2026, 6, 29))
    check("meet: lịch ngày có link buổi online", "https://meet.google.com/abc-defg-hij" in _txt)
    check("meet: lịch ngày KHÔNG link buổi tại phòng", "zzz-yyyy-xxx" not in _txt)
    _st = datetime.datetime(2026, 6, 29, 7, 30)
    _rem = _rt(_st, _st + datetime.timedelta(minutes=90), _ss[1], 10)
    check("meet: nhắc tiết có link ở dòng cuối", _rem.split("\n")[-1].endswith("https://meet.google.com/abc-defg-hij"))
    _ical = _ics(_ss)[0]
    check("meet: ICS có link đầy đủ, không có mã tại phòng",
          _ical.count("meet.google.com/abc-defg-hij") == 2 and "zzz-yyyy-xxx" not in _ical)
    # REVIEW: nhánh THEO TUẦN chỉ thấy 1 tuần -> không kiểm được "lớp có đúng 1 mã" trên cả kỳ -> KHÔNG mượn mã
    from fapc.core.schedule import fetch_week_activities as _fwa
    SUCCESS["GetActivityStudentByWeek"] = [dict(r) for r in SUCCESS["GetActivityStudent"][:2]]
    api._CACHE.clear()
    _wk = _cap(lambda: _fwa("SECRETTOKEN123", "FPTU", "HE190000", os.environ["FAP_SEMESTER"], 27, 2026))
    check("meet: TKB-theo-tuần KHÔNG mượn mã (thiếu ngữ cảnh cả kỳ)",
          len(_wk) == 2 and _wk[0].get("meetURL") == "abc-defg-hij" and not _wk[1].get("meetURL"))
finally:
    SUCCESS["GetActivityStudent"] = _saved_act
    SUCCESS.pop("GetActivityStudentByWeek", None)
    api._CACHE.clear()

# [K] 4 trường API mới (attendanceStatus · studentStatus · contents · start/endDate) — ĐƯỜNG THẬT: requests (mock)
#     -> api.call -> fetch -> bot_core.handle. Ngày TƯƠNG ĐỐI với hôm nay (±7/30 ngày) => test không thành bom hẹn giờ.
from fapc.app.bot_core import handle as _h
_keys = ("GetStudentAttendances", "GetActivityStudent", "GetApplication", "GetNotificationByRoll")
_saved4 = {k: SUCCESS.get(k) for k in _keys}
# CÙNG đồng hồ với code đang test (giờ VN, UTC+7) — KHÔNG date.today() của máy: trên máy UTC (CI, VPS) từ
# 17:00–24:00 UTC ngày VN đã sang hôm sau ⇒ /today rỗng ⇒ selftest đỏ ⇒ chặn luôn cả tự-cập-nhật của bot.
_td = api._vn_now().date()
_iso = lambda d: d.strftime("%Y-%m-%dT00:00:00")
_us = lambda d: f"{d.month}/{d.day}/{d.year} 12:00:00 AM"            # shape THẬT của GetActivityStudent.date
MODE["v"] = "success"
SUCCESS["GetStudentAttendances"] = [
    {"subjectCode": "NEW101", "attendance": 0, "numberOfTakenAttendances": 0, "numberOfAttendances": 0,
     "startDate": _iso(_td + datetime.timedelta(days=30)), "endDate": _iso(_td + datetime.timedelta(days=120)), "groupName": "G"},
    {"subjectCode": "IAP301", "attendance": 60, "numberOfTakenAttendances": 3, "numberOfAttendances": 5,
     "startDate": _iso(_td - datetime.timedelta(days=30)), "endDate": _iso(_td + datetime.timedelta(days=60)), "groupName": "G"}]
_absent_day = _td - datetime.timedelta(days=7)
SUCCESS["GetActivityStudent"] = [
    {"date": _us(_absent_day), "slotTime": "(07:30 - 09:00)", "subjectCode": "IAP301", "roomNo": "BE-304",
     "isOnline": "false", "groupName": "G", "slot": "1", "attendanceStatus": "A", "meetURL": ""},
    {"date": _us(_td), "slotTime": "(00:00 - 00:05)", "subjectCode": "IAP301", "roomNo": "BE-304",
     "isOnline": "false", "groupName": "G", "slot": "1", "attendanceStatus": "P", "meetURL": ""}]
SUCCESS["GetApplication"] = [{"name": "Đơn xin X", "createDate": "16/09/2025", "studentStatus": "1", "processNote": "ok"}]
SUCCESS["GetNotificationByRoll"] = [{"id": 7, "title": "Thông báo X", "entryDate": "2026-06-01",
                                     "contents": "Nội dung dòng 1\nDòng 2 chi tiết"}]
api._CACHE.clear()
try:
    _att = _h("attendance")
    check("api4: /attendance có ngày VẮNG từ lịch", _absent_day.strftime("%d/%m") in _att, _att[-200:])
    _new = next((l for l in _att.split("\n") if "NEW101" in l), "")
    check("api4: môn CHƯA bắt đầu không in 0% / không ⚠️", _new and "%" not in _new and "⚠️" not in _new, _new)
    _ban = _h("banrisk")
    check("api4: /banrisk giữ môn 60% đang học, bỏ môn chưa bắt đầu", "IAP301" in _ban and "NEW101" not in _ban, _ban)
    check("api4: /today đánh ✅ buổi đã điểm danh", "✅" in _h("today"))
    check("api4: /applications có huy hiệu trạng thái", "✅" in _h("applications"))
    check("api4: /notifications có trích nội dung", "💬" in _h("notifications"))
    check("api4: /notifications <id> = toàn văn", "Dòng 2 chi tiết" in _h("notifications", "7"))   # số = #id ỔN ĐỊNH
    check("api4: /notifications có số #id", "#7 · Thông báo X" in _h("notifications"))
finally:
    for _k, _v in _saved4.items():
        if _v is None: SUCCESS.pop(_k, None)
        else: SUCCESS[_k] = _v
    api._CACHE.clear()

# [L] B1 — lõi API cứng hơn, ĐƯỜNG THẬT: requests (mock) -> api.call -> check_auth/drift -> fetch -> handle.
#     Phản hồi giả có `.text` + `.headers` như requests thật. Cờ drift là 1-lần/process -> reset trước, trả lại sau.
check("drift: lưu lượng bình thường (A–K) KHÔNG bật gợi ý v2", not api._DRIFT_WARNED["done"])
class _Raw:
    def __init__(s, code, js=None, text="", ctype="application/json; charset=utf-8"):
        s.status_code, s._js, s.text, s.headers = code, js, text, {"Content-Type": ctype}
    def json(s):
        if s._js is None: raise ValueError("not json")
        return s._js
_L = {"resp": None}
def _fake_raw(url, **k):
    return _L["resp"](url.split("/MyFAP/")[1].split("?")[0])
_saved_get, _saved_drift = api.requests.get, dict(api._DRIFT_WARNED)
try:
    api.requests.get = _fake_raw
    # (1) hết phiên KIỂU v2 bọc trong HTTP 200 -> raise rõ ở CLI, bot trả lời 'refresh' (không còn [] im lặng)
    for _lbl, _body in [("code '401'", {"code": "401", "errorMessage": None, "data": None}),
                        ("errorMessage 'Unauthorized'", {"code": "200", "errorMessage": "Unauthorized", "data": []})]:
        _L["resp"] = lambda ep, b=_body: _Raw(200, b)
        api._CACHE.clear()
        raises_exit(f"v2 {_lbl}: grades.report raise", g.report)
        raises_exit(f"v2 {_lbl}: exams raise", ex.exams)
        check(f"v2 {_lbl}: bot trả lời 'refresh'", "refresh" in _cap(lambda: handle("grades")).lower())
        check(f"v2 {_lbl}: bot /all không sập", "refresh" in _cap(lambda: handle("all")).lower())
    # (2) HTTP 500 KHÔNG phải hết phiên: không raise _EXPIRED_MSG, CLI không sập
    _L["resp"] = lambda ep: _Raw(500, None, text="<html><body>Server Error</body></html>", ctype="text/html")
    api._CACHE.clear()
    no_raise("HTTP 500: grades.report không raise hết-phiên", g.report)
    check("HTTP 500: bot KHÔNG bảo refresh", "fap refresh" not in _cap(lambda: handle("grades")))
    # (3) drift: 404 + JSON (GeFeeByRoll thật) và 404-HTML của GetSemesterMark (đã 404 từ trước) -> IM
    api._DRIFT_WARNED["done"] = False
    _L["resp"] = lambda ep: (_Raw(404, {"Message": "No HTTP resource was found"}) if ep == "GeFeeByRoll"
                             else _Raw(404, None, text="<html>404</html>", ctype="text/html") if ep == "GetSemesterMark"
                             else _Raw(200, {"code": "200", "errorMessage": None, "data": "0"}))
    api._CACHE.clear()
    _e = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(_e):
        ex.fees()
        api.call("GetSemesterMark", [("CampusCode", "FPTU"), ("Authen", "SECRETTOKEN123")], "HE190000", "FPTU",
                 checksum_value=False)
    check("drift: 404-JSON / 404 đã-biết KHÔNG báo động giả", _e.getvalue() == "" and not api._DRIFT_WARNED["done"],
          _e.getvalue()[:160])
    # (4) drift THẬT (v1 bị chuyển hướng): đúng 1 gợi ý dù nhiều lệnh, không rò token/URL, lệnh vẫn trả lời
    _L["resp"] = lambda ep: _Raw(302, None, text="", ctype="text/html")
    api._CACHE.clear()
    _e = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(_e):
        _r1 = handle("grades"); _r2 = handle("attendance"); _r3 = handle("exams")
    _out = _e.getvalue()
    check("drift: 302 -> đúng 1 gợi ý song ngữ", _out.count("docs/21-api-v2.md") == 2 and "moved to API v2" in _out, _out[:200])
    check("drift: gợi ý KHÔNG rò token/URL", "SECRETTOKEN123" not in _out and "://" not in _out and "Authen" not in _out)
    check("drift: lệnh vẫn trả lời (không sập)", all(isinstance(x, str) and x for x in (_r1, _r2, _r3)))
finally:
    api.requests.get = _saved_get; api._DRIFT_WARNED.update(_saved_drift)
    MODE["v"] = "success"; api._CACHE.clear()
# (5) bộ chọn kỳ DÙNG CHUNG: dashboard (pick_semester trên list đã có) == current_semester (tự hỏi GetSemester)
_saved_sem = os.environ.pop("FAP_SEMESTER")
_saved_vn = (api._vn_now, sched._vn_now)
try:
    for _when in (datetime.datetime(2026, 8, 30, 10, 0), datetime.datetime(2026, 8, 31, 10, 0),
                  datetime.datetime(2026, 10, 3, 9, 0), datetime.datetime(2026, 12, 30, 9, 0)):
        api._vn_now = sched._vn_now = (lambda w=_when: w.replace(tzinfo=datetime.timezone.utc))
        api._CACHE.clear()
        _cur = _cap(lambda: api.current_semester("SECRETTOKEN123", "FPTU", "HE190000"))
        _pk = sched.pick_semester(SUCCESS["GetSemester"])
        check(f"semester: current_semester == pick_semester @ {_when:%d/%m %H:%M}", _cur == _pk, f"{_cur} vs {_pk}")
    check("semester: ngày cuối Summer (30/08 10:00) -> Fall như app",
          sched.pick_semester(SUCCESS["GetSemester"], datetime.datetime(2026, 8, 30, 10, 0)) == "Fall2026")
    check("semester: khe cuối năm -> Fall2026 (kỳ cuối trong list, gần nhất)", _cur == "Fall2026", _cur)
finally:
    os.environ["FAP_SEMESTER"] = _saved_sem
    api._vn_now, sched._vn_now = _saved_vn
    api._CACHE.clear()

# ---- [V2] API v2 OPT-IN (FAP_API_VERSION=v2): vòng tròn THẬT qua fetch_* -> call() -> apiv2.call_v2, mạng giả,
# khoá GIẢ "test-key", token/roll GIẢ (KHÔNG dùng creds() — trên máy thật nó đọc token.json thật).
import hmac as _hmac, hashlib as _hashlib, base64 as _b64, json as _json
import fapc.core.apiv2 as apiv2
_V2 = {"seen": [], "body": None}
def _fake_v2(url, **k):
    _V2["seen"].append((url, k))
    if not url.startswith("https://fap-proxy.fpt.edu.vn/MyFAP/"):
        raise api.requests.ConnectionError("v2 bật mà vẫn gọi host khác")
    if _V2["body"] is not None:
        return type("R", (), {"status_code": 200, "json": lambda s: _V2["body"]})()
    return _R(SUCCESS.get(url.split("/MyFAP/")[1].split("?")[0], []))
_saved_v2 = (api.requests.get, apiv2.TOKEN_JSON, os.environ.get("FAP_API_VERSION"), os.environ.get("FAP_V2_KEY"))
try:
    _tj = os.path.join(_tmp, "token_v2.json")
    with open(_tj, "w", encoding="utf-8") as _f:
        _json.dump({"authenkey": "SECRETTOKEN123", "campus": "FPTU", "rollnumber": "HE000000", "api_version": "v2"}, _f)
    apiv2.TOKEN_JSON = _tj; apiv2._SESSION_CACHE.clear()
    os.environ["FAP_API_VERSION"] = "v2"; os.environ["FAP_V2_KEY"] = "test-key"
    api.requests.get = _fake_v2; api._CACHE.clear()
    _e = io.StringIO()
    with contextlib.redirect_stdout(_e), contextlib.redirect_stderr(_e):
        _marks = g.fetch_marks("SECRETTOKEN123", "FPTU", "HE000000", "Summer2026")
        _det = aw._course_detail("SECRETTOKEN123", "FPTU", "HE000000", "Summer2026", "IAP301", "G")
    check("v2: fetch_marks qua call() -> dữ liệu", [m.get("subjectCode") for m in _marks] == ["EXE101", "IAP301"], str(_marks)[:120])
    _u, _k = _V2["seen"][0]
    check("v2: URL proxy + CampusCode, KHÔNG Authen trên query",
          _u == "https://fap-proxy.fpt.edu.vn/MyFAP/GetStudentMark?CampusCode=FPTU&rollNumber=HE000000&Semester=Summer2026", _u[:120])
    _h = _k.get("headers") or {}
    _sig, _ts = (_h.get("Checksum") or ":").rsplit(":", 1)
    _exp = _b64.b64encode(_hmac.new(b"test-key", ("SECRETTOKEN123MyFAP" + _ts).encode(), _hashlib.sha256).digest()).decode()
    check("v2: header ký đúng (Bearer + Checksum sig:ts + ClientCode/CampusCode)",
          _h.get("Authorization") == "Bearer SECRETTOKEN123" and _sig == _exp.replace("=", "%3d")
          and _h.get("ClientCode") == "MyFAP" and _h.get("CampusCode") == "FPTU" and _h.get("Content-Type") == "application/json")
    check("v2: timeout 15 + không theo redirect", _k.get("timeout") == 15 and _k.get("allow_redirects") is False)
    _u2 = _V2["seen"][1][0]
    check("v2: GetCourseAttendance viết HOA trên proxy", "/MyFAP/GetCourseAttendance?" in _u2 and "getCourseAttendance" not in _u2, _u2[:90])
    check("v2: watcher nhận list chi tiết (không None)", isinstance(_det, list))
    check("v2: khoá KHÔNG ở URL/header/log", all("test-key" not in (u + repr(k)) for u, k in _V2["seen"])
          and "test-key" not in _e.getvalue())
    # hết phiên KIỂU v2 (code '401' trong HTTP 200) -> check_auth raise như v1, KHÔNG [] im lặng
    _V2["body"] = {"code": "401", "errorMessage": "Unauthorized", "data": None}; api._CACHE.clear()
    raises_exit("v2: hết phiên -> grades raise", lambda: g.fetch_marks("SECRETTOKEN123", "FPTU", "HE000000", "Summer2026"))
    _V2["body"] = None
    # đổi lại v1 mà token vẫn mang dấu v2 -> bảo `fap refresh`, KHÔNG gọi mạng
    os.environ["FAP_API_VERSION"] = "v1"; _n = len(_V2["seen"])
    raises_exit("v2->v1 lệch phiên bản -> SystemExit", lambda: g.fetch_marks("SECRETTOKEN123", "FPTU", "HE000000", "Summer2026"))
    check("v2->v1 lệch phiên bản: 0 request", len(_V2["seen"]) == _n)
finally:
    api.requests.get, apiv2.TOKEN_JSON = _saved_v2[0], _saved_v2[1]
    os.environ["FAP_API_VERSION"] = _saved_v2[2] if _saved_v2[2] is not None else "v1"
    os.environ["FAP_V2_KEY"] = _saved_v2[3] if _saved_v2[3] is not None else ""
    apiv2._SESSION_CACHE.clear(); api._CACHE.clear()
# [L] analysis/apk_drift.py — báo cáo drift + ghi .env CHẠY TRỌN ĐƯỜNG trên bundle TỔNG HỢP + repo giả.
#     Không mạng (apk_drift không gọi mạng); kiểm MÃ THOÁT (cron/CI) + CHE (secret không lọt ra stdout).
import struct as _struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis"))
import apk_drift as _ad

_SECRET = "deadSECRET0000badf00ddeadSECRET0000badf00d"   # chuỗi TỔNG HỢP, dạng khoá (hex+chữ số)
_BASE = "https://api.fpt.edu.vn/fap/api/MyFAP"


def _blob(strings, version=96):
    storage = b""; entries = []
    for s in strings:
        raw = s.encode("utf-8"); off = len(storage); storage += raw
        assert len(raw) < 0xFF
        entries.append(_struct.pack("<I", (len(raw) << 24) | (off << 1)))
    hdr = _struct.pack("<Q", _ad.HBC_MAGIC) + _struct.pack("<I", version) + b"\x00" * 20
    u32s = [0, 0, 0, 0, 0, len(strings), 0, len(storage), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    hdr += b"".join(_struct.pack("<I", x) for x in u32s) + b"\x00"
    out = bytearray(hdr)
    def _pad(n):
        while len(out) % n: out.append(0)
    _pad(32); _pad(4); out += b"".join(entries); _pad(4); _pad(4); out += storage
    return bytes(out)


def _fake_repo():
    """Repo fapc/ TỐI GIẢN để apk_drift đọc hằng + endpoint (SECRET/BASE/CLIENT_ID… + SIMPLE + 1 call)."""
    root = tempfile.mkdtemp()
    core = os.path.join(root, "fapc", "core"); os.makedirs(core)
    open(os.path.join(root, "fapc", "__init__.py"), "w").close()
    open(os.path.join(core, "__init__.py"), "w").close()
    with open(os.path.join(core, "api.py"), "w", encoding="utf-8") as f:
        f.write("SECRET = %r\nLOGIN_PREFIX = 'loginprefix99aa'\nBASE = %r\n" % (_SECRET, _BASE))
    with open(os.path.join(core, "auth.py"), "w", encoding="utf-8") as f:
        f.write("CLIENT_ID = 'clientid_syn'\nISSUER = 'https://feid.example'\nREDIRECT_URI = 'app:/cb'\n")
    with open(os.path.join(core, "extract.py"), "w", encoding="utf-8") as f:
        f.write("SIMPLE = {'GetStudentMark': [], 'GetSemester': []}\n")
    with open(os.path.join(core, "grades.py"), "w", encoding="utf-8") as f:
        f.write("def r():\n    call('GetStudentMark', [])\n    call('GetSemester', [])\n")
    return root


_root = _fake_repo()
_present_all = [_BASE + "/GetStudentMark?campusCode=x", _BASE + "/GetSemester", _SECRET,
                "https://api.fpt.edu.vn", "clientid_syn", "https://feid.example", "app:/cb", "loginprefix99aa"]
_missing_one = [_BASE + "/GetStudentMark?campusCode=x", _SECRET, "https://api.fpt.edu.vn",
                "clientid_syn", "https://feid.example", "app:/cb", "loginprefix99aa"]   # THIẾU GetSemester
_tmp_blobs = tempfile.mkdtemp()
_pa = os.path.join(_tmp_blobs, "a.bundle"); open(_pa, "wb").write(_blob(_present_all))
_pb = os.path.join(_tmp_blobs, "b.bundle"); open(_pb, "wb").write(_blob(_missing_one))

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()):
    _rc_ok = _ad.report_one(_pa, root=_root)
_out = _buf.getvalue()
check("apk_drift: build đủ endpoint -> exit 0", _rc_ok == 0, str(_rc_ok))
check("apk_drift: SECRET tổng hợp KHÔNG lọt ra stdout (bị che)", _SECRET not in _out)
check("apk_drift: báo CÓ các hằng fap-cli", "present" in _out or "CÓ" in _out)

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()):
    _rc_bad = _ad.report_one(_pb, root=_root)
check("apk_drift: build THIẾU endpoint fap-cli gọi -> exit 1", _rc_bad == 1, str(_rc_bad))
check("apk_drift: báo cáo nêu endpoint thiếu", "GetSemester" in _buf.getvalue())

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()):
    _rc_diff = _ad.report_diff(_pb, _pa, root=_root)
_dout = _buf.getvalue()
check("apk_drift: diff (thiếu->đủ) exit 0", _rc_diff == 0, str(_rc_diff))
check("apk_drift: diff cho thấy GetSemester được THÊM", "GetSemester" in _dout)
check("apk_drift: diff không lọt SECRET", _SECRET not in _dout)

# --write-v2-key: giả lớp decode bytecode -> 1 hàm checksum v2 (HmacSHA256 + '%3d' + khoá) -> ghi .env tạm.
_syn_key = "cafeV2KEY1234beeff00dcafeV2KEY1234beeff00d"
_saved_decode = _ad._decode_functions
_env_tmp = os.path.join(_tmp_blobs, ".env.synth")
open(_env_tmp, "w", encoding="utf-8").write("FAP_LANG=vi\nFAP_CACHE_MIN=60\n")
try:
    _ad._decode_functions = lambda data: [({"HmacSHA256", "default"}, {"%3d", "+", _syn_key})]
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()):
        _rc_key = _ad.cmd_write_v2_key(_pa, _env_tmp)
    _kout = _buf.getvalue()
    check("apk_drift: write-v2-key 1 ứng viên -> exit 0", _rc_key == 0, str(_rc_key))
    check("apk_drift: write-v2-key KHÔNG in giá trị khoá", _syn_key not in _kout)
    check("apk_drift: write-v2-key in độ dài + sha", "FAP_V2_KEY" in _kout and "sha256" in _kout)
    _envlines = open(_env_tmp, encoding="utf-8").read().splitlines()
    check("apk_drift: .env giữ dòng cũ + thêm FAP_V2_KEY", "FAP_LANG=vi" in _envlines and
          any(l == "FAP_V2_KEY=" + _syn_key for l in _envlines))
    # 0 ứng viên -> từ chối exit 2, KHÔNG đụng .env
    _ad._decode_functions = lambda data: [({"foo"}, {"bar"})]
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(io.StringIO()):
        _rc_ref = _ad.cmd_write_v2_key(_pa, _env_tmp)
    check("apk_drift: write-v2-key 0 ứng viên -> exit 2 (từ chối)", _rc_ref == 2, str(_rc_ref))
finally:
    _ad._decode_functions = _saved_decode

total = OK["n"] + FAIL["n"]
print(f"=== integration_offline: {OK['n']}/{total} PASS, {FAIL['n']} FAIL ===")
sys.exit(1 if FAIL["n"] else 0)
