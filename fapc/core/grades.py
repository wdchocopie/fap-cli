#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grades.py — điểm tổng kết môn (GetStudentMark) + chi tiết thành phần (GetMarkByCourse)."""
from .api import creds, call, as_list, unwrap, current_semester, check_auth, _err_code
from . import subjects
from ..i18n import t
from .. import fmt

def fetch_marks(token, campus, roll, sem):
    http, data = call("GetStudentMark",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _gpa(rows):
    """GPA tạm tính = TB cộng các môn ĐÃ có điểm. Dùng chung fmt.has_mark/safe_float (đỡ lệch logic)."""
    graded = [fmt.safe_float(r.get("averageMark")) for r in rows if fmt.has_mark(r)]
    return round(sum(graded) / len(graded), 2) if graded else None

def term_gpa(rows):
    """(gpa, weighted). Có tín chỉ (danh mục đã cache qua `fap subjects`) → theo TRỌNG SỐ tín chỉ
    (đúng cách FPT tính); không có → rơi về TB cộng `_gpa`. THUẦN (credit lấy từ subjects memo)."""
    num = den = 0.0
    for r in rows:
        mk, cr = fmt.safe_float(r.get("averageMark")), subjects.credit_of(r.get("subjectCode", ""))
        if mk > 0 and cr > 0:
            num += mk * cr; den += cr
    if den:
        return round(num / den, 2), True
    return _gpa(rows), False

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    subjects.load()                                   # tên + tín chỉ từ cache (nếu đã `fap subjects`)
    rows = fetch_marks(token, campus, roll, sem)
    print(t(f"== Điểm kỳ {sem} ({len(rows)} môn) ==", f"== Grades {sem} ({len(rows)} subjects) =="))
    print(f"{'Môn/Subject':10} {'TB/Avg':>7}  {'Trạng thái/Status':18} {'Tên môn/Name'}")
    for r in rows:
        print(f"{r.get('subjectCode',''):10} {str(r.get('averageMark','')):>7}  "
              f"{str(r.get('status','')):18} {subjects.name(r.get('subjectCode',''))}")
    g, weighted = term_gpa(rows)
    note = t("theo tín chỉ", "credit-weighted") if weighted else t("TB cộng", "unweighted mean")
    print(t(f"\nGPA tạm tính ({note}): {fmt.gpa_val(g)}", f"\nProvisional GPA ({note}): {fmt.gpa_val(g)}"))

def _mark_params(campus, token, cid, roll, subj=None):
    """Tham số GetMarkByCourse. SubjectCode: catalog (docs/03) ghi 'có thể cần' -> gửi kèm cho chắc."""
    p = [("campusCode", campus), ("Authen", token), ("CourseId", cid), ("rollNumber", roll)]
    if subj:
        p.append(("SubjectCode", subj))
    return p

def _normalize_components(data):
    """Chuẩn hoá data GetMarkByCourse -> list dict (bỏ field 'course*'). Nhận list HOẶC dict (lấy
    mảng con nếu có, không thì coi cả dict là 1 dòng) -> không bỏ sót dữ liệu."""
    d = unwrap(data)
    if isinstance(d, dict):                       # ưu tiên list-of-dict KHÔNG rỗng (tránh lấy nhầm list 'errors' rỗng)
        _lists = [v for v in d.values() if isinstance(v, list)]
        d = next((v for v in _lists if v and isinstance(v[0], dict)), _lists[0] if _lists else [d])
    rows = d if isinstance(d, list) else []
    return [{k: v for k, v in r.items() if not str(k).lower().startswith("course")}
            for r in rows if isinstance(r, dict)]

def _components(token, campus, roll, cid, subj=None):
    """Điểm thành phần 1 môn (GetMarkByCourse theo CourseId)."""
    if not cid:
        return []
    _, data = call("GetMarkByCourse", _mark_params(campus, token, cid, roll, subj), roll, campus)
    return _normalize_components(data)

def fetch_components(token, campus, roll, cid, subj=None):
    """Như _components nhưng PHÂN BIỆT lỗi: trả None khi lấy HỎNG (mạng/token/checksum) — cho
    watch-grades giữ mốc cũ thay vì tưởng 'rỗng'."""
    if not cid:
        return []
    http, data = call("GetMarkByCourse", _mark_params(campus, token, cid, roll, subj), roll, campus)
    if http is None or _err_code(data) == "201":
        return None
    return _normalize_components(data)

def detail_text(token, campus, roll, sem, rows=None):
    """Điểm thành phần từng môn — TRẢ chuỗi (dùng cho `fap all` / web). Generic, không bịa cột.
    rows: truyền sẵn GetStudentMark để khỏi gọi lại (vd từ all_text)."""
    from .whatif import predict_course, predict_line       # import trễ: tránh vòng grades↔whatif
    from .courses import fetch_courses, course_id_map       # vá courseID/môn GetStudentMark bỏ sót
    if rows is None:
        rows = fetch_marks(token, campus, roll, sem)
    subjects.load()                                          # tên môn cho tiêu đề ▸ (nếu đã cache)
    by_code = {str(r.get("subjectCode", "")): r for r in (rows or []) if r.get("subjectCode")}
    # GetStudentMark có thể THIẾU môn (vd chỉ trả 4/6) hoặc thiếu courseID → lấy courseId mọi lớp từ
    # GetCourseOfSemester rồi HỢP nhất. Endpoint lỗi/404 → cmap rỗng → giữ nguyên hành vi cũ.
    cmap = course_id_map(fetch_courses(token, campus, roll, sem) or [])
    codes = list(by_code) + [c for c in cmap if c not in by_code]   # union: môn có điểm trước, môn bù sau
    if not codes:
        return t("🧮 Chưa có dữ liệu điểm.", "🧮 No grades yet.")
    out = [fmt.header("🧮", t(f"Điểm thành phần · {sem}", f"Component marks · {sem}"),
                      t(f"{len(codes)} môn", f"{len(codes)} subjects"))]
    for code in codes:
        r = by_code.get(code, {})
        cid = r.get("courseID") or cmap.get(code)           # courseID từ marks, else vá từ GetCourseOfSemester
        # fetch_components -> None khi LỖI (mạng/token), [] khi thật-sự-rỗng -> phân biệt 2 ca
        comps = fetch_components(token, campus, roll, cid, code)
        meta = "  ·  ".join(x for x in (str(r.get("averageMark", "")).strip(),
                                        str(r.get("status", "")).strip()) if x)   # vd '8.5 · Passed'
        out.append(f"\n▸ {subjects.label(code)}" + (f"  —  {meta}" if meta else ""))
        if comps is None:
            out.append(t("   ⚠ lỗi tải điểm thành phần (thử lại / fap refresh)",
                         "   ⚠ failed to load components (retry / fap refresh)"))
        elif comps:
            out.append(fmt.table(comps))
            out.append(predict_line(predict_course(comps)))  # 'cần X/10 ở phần còn lại để qua' (rỗng nếu thiếu trọng số)
        else:
            out.append(t("   (chưa có điểm thành phần)", "   (no component marks yet)"))
    return "\n".join(l for l in out if l != "")             # bỏ dòng predict rỗng

def _detail_raw(token, campus, roll, sem):
    """In NGUYÊN response GetMarkByCourse từng môn — để soi vì sao 'chưa có' (rỗng thật vs sai shape)."""
    import json
    for r in fetch_marks(token, campus, roll, sem):
        cid = r.get("courseID")
        http, data = call("GetMarkByCourse", _mark_params(campus, token, cid, roll, r.get("subjectCode")), roll, campus)
        d = data.get("data") if isinstance(data, dict) else data
        shape = type(d).__name__ + (f"[{len(d)}]" if isinstance(d, (list, dict)) else "")
        print(f"\n# {r.get('subjectCode')}  courseID={cid}  HTTP {http}  data={shape}")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])

def detail(raw=False):
    """Điểm thành phần từng môn (GetMarkByCourse theo courseID). raw=True -> in JSON gốc để chẩn đoán."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    if raw:
        _detail_raw(token, campus, roll, sem)
    else:
        print(detail_text(token, campus, roll, sem))
