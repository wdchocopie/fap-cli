#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_smoke.py — KIỂM THỬ THẬT (gọi api.fpt.edu.vn) bằng tài khoản của bạn.

KHÁC test_logic.py (offline): file này GỌI API THẬT để xác nhận end-to-end mọi lệnh.
Cần: đã `fap login` (token còn hạn — chạy `fap refresh` trước nếu cần).

Chạy (từ gốc repo):
    python tests/live_smoke.py              # kiểm endpoint + render (KHÔNG gửi tin)
    python tests/live_smoke.py --channels   # + gửi 1 tin thử lên Telegram/Discord

Nó cũng TỰ DÒ checksum đúng cho GetMarkByCourse (lệnh `grades-detail`) — xem mục [grades-detail].
Dán toàn bộ output cho người hỗ trợ nếu có endpoint nào ✗ / code=201.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fapc.core.api import creds, current_semester, call, checksum_auth, checksum_login, as_list, unwrap

_results = []

def _summ(http, data):
    code = data.get("code") if isinstance(data, dict) else None
    d = unwrap(data)
    n = len(d) if isinstance(d, (list, dict)) else "-"
    return http, code, n

def check(name, fn):
    try:
        print(f"  OK   {name}: {fn()}")
        _results.append(True)
    except SystemExit as e:
        print(f"  ✗    {name}: {e}"); _results.append(False)
    except Exception as e:                      # noqa: BLE001
        print(f"  ✗    {name}: {type(e).__name__}: {e}"); _results.append(False)

def probe_auth():
    """Dò phản hồi THẬT khi token sai + checksum lệch giờ (để chốt logic phát hiện token-hết-hạn / retry)."""
    import datetime
    from fapc.core.api import checksum_auth, _vn_now
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print("[PROBE 1] Token SAI/hết hạn (gửi Authen rác):")
    http, data = call("GetStudentMark",
        [("campusCode", campus), ("Authen", "EXPIRED_GARBAGE"), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    code = data.get("code") if isinstance(data, dict) else None
    print(f"    -> HTTP {http} code={code} body={str(data)[:200]}")
    print("\n[PROBE 2] Checksum LỆCH GIỜ (giờ VN - 1h):")
    cs = checksum_auth(roll, campus, when=_vn_now() - datetime.timedelta(hours=1))
    http2, data2 = call("GetStudentMark",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus,
        checksum_value=cs)
    code2 = data2.get("code") if isinstance(data2, dict) else None
    print(f"    -> HTTP {http2} code={code2} body={str(data2)[:200]}")
    print("\n=> Dán 2 dòng '-> HTTP ...' này lại để chốt logic check_auth + retry-checksum.")

def main():
    if "--probe-auth" in sys.argv:
        probe_auth(); return
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print(f"== Tài khoản: roll={roll} campus={campus} kỳ={sem} ==\n")

    def ep(endpoint, params, cv=None):
        http, data = call(endpoint, params, roll, campus, checksum_value=cv)
        h, code, n = _summ(http, data)
        flag = "" if (h == 200 and str(code) in ("200", "None")) else "  ⚠️ code bất thường"
        return f"HTTP {h} code={code} items={n}{flag}"

    print("[1] Endpoint READ:")
    P = lambda *ks: [(k, {"campusCode": campus, "Authen": token, "Semester": sem,
                          "rollNumber": roll}[k]) for k in ks]
    check("GetActivityStudent  (schedule/ics/today/week)", lambda: ep("GetActivityStudent", P("campusCode", "Authen", "Semester", "rollNumber")))
    check("GetStudentMark      (grades/whatif)", lambda: ep("GetStudentMark", P("campusCode", "Authen", "Semester", "rollNumber")))
    check("GetStudentAttendances (attendance/banrisk/watch)", lambda: ep("GetStudentAttendances", P("campusCode", "Authen", "Semester", "rollNumber")))
    check("AcademicTranscript  (transcript)", lambda: ep("AcademicTranscript", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)]))

    # ---- [grades-detail] tự dò checksum đúng cho GetMarkByCourse ----
    print("\n[2] grades-detail — dò checksum GetMarkByCourse:")
    _, gm = call("GetStudentMark", P("campusCode", "Authen", "Semester", "rollNumber"), roll, campus)
    rows = as_list(gm)
    if not rows:
        print("    (không có môn nào trong GetStudentMark — bỏ qua)")
    else:
        cid, subj = rows[0].get("courseID"), rows[0].get("subjectCode")
        base = [("campusCode", campus), ("Authen", token), ("CourseId", cid), ("rollNumber", roll)]
        print(f"    môn thử: {subj} (courseID={cid})")
        candidates = {
            "cs12(rollNumber, campus) [đang dùng]": checksum_auth(roll, campus),
            "cs12(CourseId, campus)": checksum_auth(cid, campus),
            "cs12(campus, rollNumber)": checksum_auth(campus, roll),
            "cs14(campus) [login]": checksum_login(campus),
            "KHÔNG checksum": False,
        }
        winner = winner_cv = None
        for label, cv in candidates.items():
            http, data = call("GetMarkByCourse", base, roll, campus, checksum_value=cv)
            h, code, n = _summ(http, data)
            ok = (h == 200 and str(code) == "200")
            if ok and winner is None:
                winner, winner_cv = label, cv
            print(f"      {label:36} HTTP {h} code={code} items={n}{'  ← ĐÚNG ✅' if ok else ''}")
        print(f"    => Checksum đúng: {winner or 'KHÔNG cái nào trả 200 (báo lại để tìm tiếp)'}")
        # In MẪU field điểm thành phần (trả lời 'có lấy được điểm thành phần không?')
        if winner:
            _, data = call("GetMarkByCourse", base, roll, campus, checksum_value=winner_cv)
            comps = as_list(data)
            if comps:
                print(f"    điểm thành phần ({len(comps)}): {list(comps[0].keys())}")
                print(f"      ví dụ: {comps[0]}")
            else:
                print("    (server trả RỖNG — môn chưa nhập điểm thành phần; cấu trúc sẽ hiện khi có điểm)")

    # ---- [3] render text từng lệnh (qua bot_core) ----
    print("\n[3] Render lệnh (dòng đầu mỗi tin):")
    from fapc.app.bot_core import handle
    for cmd in ["today", "week", "grades", "grades-detail", "attendance", "banrisk", "status", "whatif", "exams", "all"]:
        check(f"/{cmd}", lambda cmd=cmd: (handle(cmd).splitlines() or [""])[0])

    # ---- [4] watcher 1 lượt (không gửi) ----
    print("\n[4] watch-attendance (1 lượt, không gửi):")
    from fapc.app.attendwatch import poll
    check("poll()", lambda: f"{poll(notify=False)} buổi mới (lần đầu = 0, đã ghi mốc)")

    # ---- [5] kênh chat (chỉ khi --channels) ----
    print("\n[5] Kênh Telegram/Discord:")
    if "--channels" in sys.argv:
        from fapc.app.notify import push
        sent = push("✅ FAP live smoke test — kênh hoạt động.")
        print(f"    đã gửi tới: {sent or '(chưa cấu hình kênh — sửa .env)'}")
    else:
        print("    (bỏ qua — thêm cờ --channels để gửi tin thử thật)")

    ok = sum(_results); tot = len(_results)
    print(f"\n=== {ok}/{tot} mục OK ===")
    if ok < tot:
        print("Có mục ✗/⚠️ — nếu là 401/201: chạy `fap refresh` rồi thử lại, hoặc báo lại output.")

if __name__ == "__main__":
    main()
