#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transcript.py — Bảng điểm tích lũy (AcademicTranscript).

    fap transcript

Nguồn: AcademicTranscript (cs12 rollNumber,campusCode). Tài khoản chưa hoàn tất kỳ nào
thì server trả rỗng — khi đó in thông báo thay vì lỗi. Cột hiển thị theo đúng field server trả.
"""
from .api import creds, call, as_list, check_auth
from ..i18n import t
from .. import fmt

def fetch(token, campus, roll):
    http, data = call("AcademicTranscript",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)        # token hết hạn -> raise rõ thay vì "chưa có bảng điểm"
    return as_list(data)

def report():
    token, campus, roll = creds()
    rows = fetch(token, campus, roll)
    if not rows:
        print(t("Chưa có bảng điểm tích lũy — tài khoản chưa hoàn tất kỳ nào, hoặc server trả rỗng.",
                "No academic transcript yet — no completed semester, or the server returned empty."))
        return
    print(t(f"== Bảng điểm tích lũy ({len(rows)} dòng) ==", f"== Academic transcript ({len(rows)} rows) =="))
    print(fmt.table(rows))        # bảng generic dùng chung (fmt.table) — không bịa cột

# ---------- GPA tích lũy (theo TÍN CHỈ — đúng cách FPT tính) ----------
def _weighted_gpa(rows):
    """GPA = Σ(điểm×tín chỉ) / Σ(tín chỉ) trên các môn ĐÃ có điểm & có tín chỉ. None nếu chưa đủ dữ liệu.
    GetSemesterMark hay 404 nên nguồn chuẩn nhất là AcademicTranscript (có averageMark + credit)."""
    num = den = 0.0
    for r in rows:
        mk, cr = fmt.safe_float(r.get("averageMark")), fmt.safe_float(r.get("credit"))
        if mk > 0 and cr > 0:
            num += mk * cr; den += cr
    return round(num / den, 2) if den else None

def gpa_text(token, campus, roll):
    """GPA tích lũy theo tín chỉ (toàn khoá + từng kỳ). KHÁC GPA tạm tính của `whatif` (TB cộng kỳ hiện tại)."""
    rows = fetch(token, campus, roll)
    if not rows:
        return t("📈 Chưa có GPA tích lũy — chưa hoàn tất kỳ nào (sẽ có sau khi học xong kỳ đầu).",
                 "📈 No cumulative GPA yet — no completed semester (appears after your first finished term).")
    lines = [fmt.header("📈", t("GPA tích lũy (theo tín chỉ)", "Cumulative GPA (credit-weighted)"))]
    sems = {}
    for r in rows:
        sems.setdefault(r.get("semesterName") or "?", []).append(r)
    for sem, rs in sems.items():
        lines.append(f"• {sem}: {fmt.gpa_val(_weighted_gpa(rs))}  ({len(rs)} " + t("môn", "subj") + ")")
    overall = _weighted_gpa(rows)
    lines.append("\n" + t(f"🎓 GPA toàn khoá: {fmt.gpa_val(overall)}  ({len(rows)} môn)",
                          f"🎓 Overall GPA: {fmt.gpa_val(overall)}  ({len(rows)} subjects)"))
    return "\n".join(lines)

def gpa_report():
    token, campus, roll = creds()
    print(gpa_text(token, campus, roll))

def main():
    report()

if __name__ == "__main__":
    main()
