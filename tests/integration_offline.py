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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FAP_SEMESTER"] = "Summer2026"; os.environ["FAP_LANG"] = "vi"

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
    return _R(SUCCESS.get(ep, []))
api.requests.get = fake_get; api._CACHE.clear()
try: api.creds()
except SystemExit: api.creds = lambda: ("SECRETTOKEN123", "FPTU", "HE190000")
import fapc.app.notify as notify
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
for c in COMMANDS:
    if c != "help": no_raise(f"handle/{c}", lambda c=c: handle(c, "8" if c == "whatif" else None))
for lbl, fn in [("grades.report", g.report), ("grades.detail", g.detail), ("grades.detail.raw", lambda: g.detail(raw=True)), ("att.report", at.report), ("banrisk", at.banrisk), ("transcript", tr.report), ("gpa", tr.gpa_report), ("whatif", lambda: wi.run("8")), ("status", db.status), ("week", lambda: db.week(None)), ("exams", ex.exams), ("news", ex.news), ("fees", ex.fees), ("notifications", ex.notifications), ("exams_ics", ex.exams_ics)]:
    no_raise("ok:" + lbl, fn)
# [C] token hết hạn
MODE["v"] = "expired"; api._CACHE.clear()
for lbl, fn in [("grades", g.report), ("att", at.report), ("gpa", tr.gpa_report), ("exams", ex.exams), ("fees", ex.fees), ("notif", ex.notifications)]:
    raises_exit("expired:" + lbl, fn)
MODE["v"] = "success"; api._CACHE.clear()
check("grades-detail merges GetCourseOfSemester subject (P7)", "FRS401c" in _cap(lambda: handle("grades-detail")))
check("courses roster renders (P8)", "IAP301" in _cap(lambda: handle("courses")))
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
check("gradewatch 2-cycle detects", f0 and any("9.0" in e for e in ev1))
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

total = OK["n"] + FAIL["n"]
print(f"=== integration_offline: {OK['n']}/{total} PASS, {FAIL['n']} FAIL ===")
sys.exit(1 if FAIL["n"] else 0)
