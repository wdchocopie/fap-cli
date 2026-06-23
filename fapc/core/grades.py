#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grades.py — điểm tổng kết môn (GetStudentMark) + chi tiết thành phần (GetMarkByCourse)."""
from .api import creds, call, as_list, unwrap, current_semester, check_auth, _err_code
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

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = fetch_marks(token, campus, roll, sem)
    print(t(f"== Điểm kỳ {sem} ({len(rows)} môn) ==", f"== Grades {sem} ({len(rows)} subjects) =="))
    print(f"{'Môn/Subject':12} {'Lớp/Class':14} {'TB/Avg':>7}  {'Trạng thái/Status'}")
    for r in rows:
        print(f"{r.get('subjectCode',''):12} {r.get('className',''):14} {str(r.get('averageMark','')):>7}  {r.get('status','')}")
    g = fmt.gpa_val(_gpa(rows))
    print(t(f"\nGPA tạm tính (môn đã có điểm): {g}", f"\nProvisional GPA (graded subjects): {g}"))

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
    if rows is None:
        rows = fetch_marks(token, campus, roll, sem)
    if not rows:
        return t("🧮 Chưa có dữ liệu điểm.", "🧮 No grades yet.")
    out = [fmt.header("🧮", t(f"Điểm thành phần · {sem}", f"Component marks · {sem}"),
                      t(f"{len(rows)} môn", f"{len(rows)} subjects"))]
    for r in rows:
        comps = _components(token, campus, roll, r.get("courseID"), r.get("subjectCode"))
        out.append(f"\n▸ {r.get('subjectCode','')}")
        out.append(fmt.table(comps) if comps else t("   (chưa có điểm thành phần)", "   (no component marks yet)"))
    return "\n".join(out)

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
