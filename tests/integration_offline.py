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

total = OK["n"] + FAIL["n"]
print(f"=== integration_offline: {OK['n']}/{total} PASS, {FAIL['n']} FAIL ===")
sys.exit(1 if FAIL["n"] else 0)
