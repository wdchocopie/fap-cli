#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transcript.py — Bảng điểm tích lũy (AcademicTranscript).

    fap transcript

Nguồn: AcademicTranscript (cs12 rollNumber,campusCode). Tài khoản chưa hoàn tất kỳ nào
thì server trả rỗng — khi đó in thông báo thay vì lỗi. Cột hiển thị theo đúng field server trả.
"""
import re
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

# ---------- Xu hướng GPA theo kỳ (gpa-trend) ----------
_SEASON = {"spring": 1, "summer": 2, "fall": 3, "autumn": 3}
_SPARK = "▁▂▃▄▅▆▇█"

def _sem_key(name):
    """THUẦN: 'Spring2026' → (năm, thứ-tự-mùa) để sắp xếp kỳ theo thời gian. Không parse được → (9999, 9, tên)."""
    s = str(name or "").strip()
    m = re.match(r"([A-Za-z]+)\s*0*(\d{4})", s)
    if not m:
        return (9999, 9, s)
    return (int(m.group(2)), _SEASON.get(m.group(1).lower(), 8), s)

def _sparkline(vals):
    """THUẦN: sparkline unicode từ list số (None → khoảng trắng). '' nếu < 2 điểm số."""
    xs = [v for v in vals if v is not None]
    if len(xs) < 2:
        return ""
    lo, hi = min(xs), max(xs)
    if hi == lo:
        return _SPARK[len(_SPARK) // 2] * len(vals)
    return "".join(" " if v is None else _SPARK[int((v - lo) / (hi - lo) * (len(_SPARK) - 1) + 0.5)] for v in vals)

def trend_text(rows):
    """THUẦN: GPA mỗi kỳ (theo tín chỉ) + delta so kỳ trước + sparkline + GPA toàn khoá.
    Trả lời câu 'mình đang lên hay xuống?' mà gpa/transcript (phẳng) đang giấu."""
    if not rows:
        return t("📈 Chưa có dữ liệu xu hướng GPA (chưa hoàn tất kỳ nào).",
                 "📈 No GPA trend yet (no completed semester).")
    sems = {}
    for r in rows:
        sems.setdefault(str(r.get("semesterName") or "?"), []).append(r)
    order = sorted(sems, key=_sem_key)
    gpas = [_weighted_gpa(sems[s]) for s in order]
    lines = [fmt.header("📈", t("Xu hướng GPA theo kỳ", "GPA trend by semester"))]
    prev = None
    for s, g in zip(order, gpas):
        if g is None:
            lines.append(f"• {s}: {fmt.gpa_val(None)}"); continue
        tail = ""
        if prev is not None:
            d = round(g - prev, 2)
            tail = f"  {'▲' if d > 0 else '▼' if d < 0 else '▬'}{abs(d):.2f}" if d else "  ▬"
        lines.append(f"• {s}: {g}{tail}  ({len(sems[s])} " + t("môn", "subj") + ")")
        prev = g
    spark = _sparkline(gpas)
    if spark:
        lines.append("\n" + t("Đồ thị: ", "Trend: ") + spark)
    lines.append(t(f"🎓 GPA toàn khoá: {fmt.gpa_val(_weighted_gpa(rows))}",
                   f"🎓 Overall GPA: {fmt.gpa_val(_weighted_gpa(rows))}"))
    return "\n".join(lines)

def trend_report():
    token, campus, roll = creds()
    print(trend_text(fetch(token, campus, roll)))

def main():
    report()

if __name__ == "__main__":
    main()
