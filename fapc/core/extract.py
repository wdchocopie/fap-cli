#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py — KÉO TOÀN BỘ dữ liệu đọc-được của tài khoản bạn về output/.

  A) Dữ liệu cục bộ RKStorage (chỉ khi dùng hướng máy ảo)  -> output/local_data.json
  B) Mọi endpoint READ-ONLY                                -> output/api/<endpoint>.json
  C) Chi tiết điểm danh từng môn (getCourseAttendance)     -> output/api/courseAttendance__<mã>.json

Bỏ qua các endpoint GHI dữ liệu (AddRate, UpdateToken...). Chỉ dùng cho TÀI KHOẢN CỦA CHÍNH BẠN.

Chạy (từ thư mục gốc repo):
    fap login       # nếu chưa có token
    fap extract
"""
import os, json, time, sqlite3
from .api import creds, call, unwrap, as_list, current_semester, checksum_auth, checksum_login, _vn_now, DB

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output")
APIOUT = os.path.join(OUT, "api")

# Endpoint read-only -> các tham số cơ bản cần gửi (checksum tự thêm).
SIMPLE = {
    "GetAllActiveCampus":     [],
    "GetSemester":            ["campusCode", "Authen"],
    "GetCampusInfo":          ["campusCode", "Authen", "rollNumber"],
    "GetStudentById":         ["campusCode", "Authen", "rollNumber"],
    "CheckUpdateProfile":     ["campusCode", "Authen", "rollNumber"],
    "AcademicTranscript":     ["campusCode", "Authen", "rollNumber"],
    "GetStudentMark":         ["campusCode", "Authen", "Semester", "rollNumber"],
    "GetSemesterMark":        ["CampusCode", "Authen", "rollNumber"],
    "GetSubjets":             ["campusCode", "Authen"],
    "GetSubjectBySemester":   ["campusCode", "Authen", "Semester"],
    "GetScheduleExam":        ["campusCode", "rollNumber", "Semester", "Authen"],
    "GetStudentAttendances":  ["campusCode", "Authen", "Semester", "rollNumber"],
    "GetBalance":             ["campusCode", "Authen", "rollNumber"],
    "GeFeeByRoll":            ["campusCode", "Authen", "rollNumber"],
    "GetActivityStudent":     ["campusCode", "Authen", "Semester", "rollNumber"],
    "GetDiemphongtrao":       ["campusCode", "Authen", "rollNumber", "semester"],
    "GetStudentRate":         ["campusCode", "Authen", "rollNumber"],
    "CheckOpenFeedBack":      ["campusCode", "Authen", "rollNumber"],
    "GetApplication":         ["campusCode", "Authen", "rollNumber"],
    "GetNotificationByRoll":  ["campusCode", "Authen", "rollNumber"],
    "GetTop10News":           ["campusCode", "Authen", "type"],
}

def save(name, http, data):
    with open(os.path.join(APIOUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"http": http, "data": data}, f, ensure_ascii=False, indent=2)
    code = data.get("code") if isinstance(data, dict) else None
    d = unwrap(data)
    n = len(d) if isinstance(d, (list, dict)) else "-"
    flag = "OK" if (http == 200 and str(code) in ("200", "None")) else f"! code={code}"
    print(f"  {name:24} HTTP {http} items={str(n):>4}  {flag}")

def main():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print(f"== Tài khoản: campus={campus} roll={roll} token={token[:8]}… kỳ={sem} ==")
    os.makedirs(APIOUT, exist_ok=True)
    try: DELAY = max(0.0, float(os.environ.get("FAP_EXTRACT_DELAY", "0.7")))   # nghỉ giữa lượt (nhẹ tay server)
    except (TypeError, ValueError): DELAY = 0.7
    VAL = {"campusCode": campus, "CampusCode": campus, "rollNumber": roll, "roll": roll,
           "Semester": sem, "semester": sem, "Authen": token, "type": "0"}
    # checksum đặc biệt (reverse từ bytecode) — khác mặc định (rollNumber, campusCode):
    CK = {
        "GetSemester":          lambda: checksum_login(campus),
        "GetSubjets":           lambda: checksum_login(campus),
        "GetSubjectBySemester": lambda: checksum_auth(sem, campus),
        "GetTop10News":         lambda: checksum_auth(VAL["type"], campus),
        "GetSemesterMark":      lambda: False,          # app không gửi checksum
    }

    # ---- A) Dữ liệu cục bộ (chỉ khi có RKStorage; hướng OAuth thì bỏ qua) ----
    print("\n[A] Dữ liệu cục bộ (RKStorage):")
    if os.path.exists(DB):
        con = sqlite3.connect(DB); cur = con.cursor()
        cur.execute("SELECT key, value FROM catalystLocalStorage")
        local = {}
        for k, v in cur.fetchall():
            try: local[k] = json.loads(v)
            except Exception: local[k] = v
        con.close()
        with open(os.path.join(OUT, "local_data.json"), "w", encoding="utf-8") as f:
            json.dump(local, f, ensure_ascii=False, indent=2)
        print(f"  {len(local)} key -> output/local_data.json")
    else:
        print("  (bỏ qua — không có RKStorage; dữ liệu lấy qua API ở [B])")

    # ---- B) Endpoint read-only ----
    print("\n[B] API read-only:")
    subjects = marks = []
    for i, (ep, keys) in enumerate(SIMPLE.items()):
        if i: time.sleep(DELAY)              # nghỉ TRƯỚC mỗi lượt trừ lượt đầu -> bỏ luôn sleep cuối thừa
        params = [(k, VAL[k]) for k in keys]
        cv = CK[ep]() if ep in CK else None
        http, data = call(ep, params, roll, campus, checksum_value=cv)
        save(ep, http, data)
        if ep == "GetStudentAttendances":
            subjects = as_list(data)         # ép list — tránh sập nếu trả dict lỗi/token hết hạn
        elif ep == "GetStudentMark":
            marks = as_list(data)

    # ---- C) Chi tiết điểm danh theo từng môn ----
    print(f"\n[C] getCourseAttendance theo {len(subjects)} môn:")
    if not subjects:
        print("  (không có môn — token hết hạn hoặc kỳ không đúng?)")
    for i, s in enumerate(subjects):
        if i: time.sleep(DELAY)
        params = [("campusCode", campus), ("rollNumber", roll), ("Semester", sem),
                  ("ClassName", s.get("groupName")), ("SubjectCode", s.get("subjectCode")), ("Authen", token)]
        http, data = call("getCourseAttendance", params, roll, campus)
        save(f"courseAttendance__{s.get('subjectCode')}", http, data)

    # ---- D) Điểm thành phần theo từng môn (GetMarkByCourse theo courseID) ----
    print(f"\n[D] GetMarkByCourse theo {len(marks)} môn:")
    if not marks:
        print("  (không có môn — token hết hạn hoặc kỳ không đúng?)")
    for i, r in enumerate(marks):
        cid = r.get("courseID")
        if not cid:
            continue
        if i: time.sleep(DELAY)
        params = [("campusCode", campus), ("Authen", token), ("CourseId", cid), ("rollNumber", roll),
                  ("SubjectCode", r.get("subjectCode"))]   # catalog: GetMarkByCourse 'có thể cần SubjectCode'
        http, data = call("GetMarkByCourse", params, roll, campus)
        save(f"markByCourse__{r.get('subjectCode')}", http, data)

    # ---- E) TKB theo tuần (GetWeekByDate -> GetActivityStudentByWeek) — bắt raw để có ground truth ----
    print("\n[E] TKB theo tuần:")
    try:
        today = _vn_now().date()
        wb_http, wb = call("GetWeekByDate", [("campusCode", campus), ("Authen", token),
            ("rollNumber", roll), ("date", today.strftime("%Y-%m-%d"))], roll, campus)
        save("GetWeekByDate", wb_http, wb)
        wbd = unwrap(wb) if isinstance(unwrap(wb), dict) else {}
        wk, yr = wbd.get("week") or wbd.get("Week"), wbd.get("year") or wbd.get("Year") or today.year
        if wk:
            time.sleep(DELAY)
            ba_http, ba = call("GetActivityStudentByWeek", [("campusCode", campus), ("Authen", token),
                ("Semester", sem), ("rollNumber", roll), ("week", str(wk)), ("year", str(yr))], roll, campus)
            save("GetActivityStudentByWeek", ba_http, ba)
        else:
            print("  (GetWeekByDate không trả số tuần — bỏ qua GetActivityStudentByWeek)")
    except Exception as e:                       # noqa: BLE001 — endpoint mới, đừng làm hỏng cả extract
        print("  (bỏ qua TKB-tuần:", e, ")")

    print("\n=> Xong. Toàn bộ nằm trong output/")
    print("⚠️  output/ chứa ĐIỂM / HỌC BẠ / TÀI CHÍNH / HỒ SƠ cá nhân — KHÔNG chia sẻ hay đẩy lên repo công khai.")

if __name__ == "__main__":
    main()
