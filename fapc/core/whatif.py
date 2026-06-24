#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""whatif.py — Mô phỏng GPA: cần bao nhiêu điểm ở các môn còn lại để đạt mục tiêu.

    fap whatif        # bảng dự kiến GPA nếu các môn còn lại đạt 5..10
    fap whatif 8      # cần TB bao nhiêu trên các môn còn lại để GPA = 8

LƯU Ý: ước tính theo TRUNG BÌNH CỘNG đơn giản giữa các môn (thang 0–10). GPA thật của
FPT tính theo TÍN CHỈ — dữ liệu GetStudentMark không kèm số tín chỉ nên đây là xấp xỉ.
"""
from .api import creds, current_semester
from .grades import fetch_marks
from ..i18n import t
from .. import fmt

MARK_MAX = 10.0
PASS_MARK = 5.0                           # ngưỡng qua môn FPT (điểm trung bình môn ≥ 5)
WHATIF_STEPS = (5, 6, 7, 8, 9, 10)        # dải mốc dùng chung CLI + bot (tránh lệch 5–10 vs 6–10)

# Field "trọng số" / "giá trị" của 1 đầu điểm khác nhau theo campus → dò generic (giống gradewatch).
_WEIGHT_KEYS = {"weight", "weightvalue", "weightpercent", "percent", "weightstr"}
_VALUE_KEYS = {"value", "mark", "grade", "score", "point", "averagemark", "result", "valuestr"}

def _num(x):
    try:
        return float(str(x).replace("%", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return None

def _field(c, keys):
    for k in c:
        if str(k).lower() in keys and c[k] not in (None, ""):
            return c[k]
    return None

def predict_course(components, target=PASS_MARK, max_mark=MARK_MAX):
    """THUẦN — cho điểm thành phần 1 MÔN: cần TB bao nhiêu ở các đầu điểm CHƯA có để môn đạt `target`.
    Trọng số tự triệt tiêu nên không cần biết % hay phân số. Trả dict hoặc None nếu không đọc được trọng số.
      {locked, total_w, remaining_w, remaining_pct, needed, guaranteed, impossible, current}"""
    total_w = locked = 0.0
    any_w = False
    for c in components:
        if not isinstance(c, dict):
            continue
        w = _num(_field(c, _WEIGHT_KEYS))
        if w is None or w <= 0:
            continue
        any_w = True
        total_w += w
        v = _num(_field(c, _VALUE_KEYS))      # None = đầu điểm chưa có giá trị
        if v is not None:
            locked += v * w
    if not any_w or total_w <= 0:
        return None
    graded_w = sum(_num(_field(c, _WEIGHT_KEYS)) or 0 for c in components
                   if isinstance(c, dict) and _num(_field(c, _VALUE_KEYS)) is not None
                   and (_num(_field(c, _WEIGHT_KEYS)) or 0) > 0)
    remaining_w = total_w - graded_w
    current = round(locked / total_w, 2)              # điểm môn nếu phần còn lại = 0
    if remaining_w <= 0:
        return {"locked": locked, "total_w": total_w, "remaining_w": 0.0, "remaining_pct": 0.0,
                "needed": 0.0, "guaranteed": current >= target, "impossible": current < target, "current": current}
    needed = (target * total_w - locked) / remaining_w
    return {"locked": locked, "total_w": total_w, "remaining_w": remaining_w,
            "remaining_pct": round(100 * remaining_w / total_w, 1), "needed": round(needed, 2),
            "guaranteed": needed <= 0, "impossible": needed > max_mark + 1e-9, "current": current}

def predict_line(pred, target=PASS_MARK):
    """THUẦN — 1 dòng người-đọc cho kết quả predict_course (None → '')."""
    if not pred:
        return ""
    if pred["remaining_w"] <= 0:
        return (t(f"   📊 Đã chốt: {pred['current']}/10 → {'QUA' if pred['guaranteed'] else 'CHƯA qua'} (≥{target:g})",
                  f"   📊 Final: {pred['current']}/10 → {'PASS' if pred['guaranteed'] else 'NOT passed'} (≥{target:g})"))
    if pred["guaranteed"]:
        return t(f"   📊 Đã chắc QUA môn (kể cả 0đ ở {pred['remaining_pct']:g}% còn lại).",
                 f"   📊 Already secured a PASS (even with 0 on the remaining {pred['remaining_pct']:g}%).")
    if pred["impossible"]:
        return t(f"   📊 Cần {pred['needed']}/10 ở {pred['remaining_pct']:g}% còn lại để qua — vượt 10, rất khó.",
                 f"   📊 Need {pred['needed']}/10 on the remaining {pred['remaining_pct']:g}% — above 10, very hard.")
    return t(f"   📊 Cần TB {pred['needed']}/10 ở {pred['remaining_pct']:g}% trọng số còn lại để qua (≥{target:g}).",
             f"   📊 Need avg {pred['needed']}/10 on the remaining {pred['remaining_pct']:g}% weight to pass (≥{target:g}).")

def _split(rows):
    """-> (graded[(code,mark)], sum_graded, remaining_count). 'remaining' = môn chưa có điểm (avg=0)."""
    graded, sg, remaining = [], 0.0, 0
    for r in rows:
        v = fmt.safe_float(r.get("averageMark"))
        if v > 0:
            graded.append((r.get("subjectCode", ""), v)); sg += v
        else:
            remaining += 1
    return graded, sg, remaining

def needed_average(target, sum_graded, n_total, remaining):
    """Điểm TB cần trên các môn còn lại để toàn kỳ đạt 'target'. None nếu không còn môn nào."""
    if remaining <= 0:
        return None
    return (target * n_total - sum_graded) / remaining

def run(target=None):
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = fetch_marks(token, campus, roll, sem)
    graded, sg, remaining = _split(rows)
    n_total = len(graded) + remaining

    print(t(f"== Mô phỏng GPA — kỳ {sem} ==", f"== GPA what-if — {sem} =="))
    print(t(f"Đã có điểm: {len(graded)} | đang học (chưa điểm): {remaining} | tổng: {n_total} môn",
            f"Graded: {len(graded)} | in-progress: {remaining} | total: {n_total} subjects"))
    print(t("(Xấp xỉ TRUNG BÌNH CỘNG giữa các môn, thang 0–10. GPA thật của FPT tính theo tín chỉ.)",
            "(Simple unweighted mean across subjects, 0–10 scale. Real FPT GPA is credit-weighted.)"))
    if n_total == 0:
        print(t("Không có môn nào trong kỳ.", "No subjects this term.")); return

    if graded:
        print(t(f"GPA hiện tại (môn đã có điểm): {round(sg/len(graded), 2)}",
                f"Current GPA (graded only): {round(sg/len(graded), 2)}"))
    if remaining == 0:
        print(t("Tất cả môn đã có điểm — GPA kỳ đã chốt.", "All subjects graded — term GPA is final.")); return

    tgt = None
    if target is not None:
        try: tgt = float(str(target).replace(",", "."))
        except ValueError: tgt = None
    if target is not None and tgt is None:        # gõ mục tiêu nhưng không đọc được -> báo, đừng nuốt im
        print(t(f'Không đọc được mục tiêu "{target}" — hiển thị bảng dự kiến.',
                f'Could not parse target "{target}" — showing projection table.'))

    if tgt is None:
        print(t("\nNếu các môn còn lại đạt trung bình → GPA kỳ dự kiến:",
                "\nIf the remaining subjects average → projected term GPA:"))
        for m in WHATIF_STEPS:
            proj = (sg + m * remaining) / n_total
            print(f"   {m:>2}/10  ->  {round(proj, 2)}")
        print(t("\nMẹo: `fap whatif 8` để biết cần bao nhiêu nhằm đạt GPA 8.",
                "\nTip: `fap whatif 8` to see what you need to reach GPA 8."))
        return

    need = needed_average(tgt, sg, n_total, remaining)
    print(t(f"\nĐể GPA cả {n_total} môn đạt {round(tgt, 2)}:",
            f"\nTo reach GPA {round(tgt, 2)} across {n_total} subjects:"))
    if need > MARK_MAX:
        print(t(f"   ✗ Cần TB {round(need, 2)} trên {remaining} môn còn lại — vượt thang 10, không khả thi.",
                f"   ✗ Need avg {round(need, 2)} on the {remaining} remaining — above 10, not feasible."))
    elif need <= 0:
        print(t("   ✓ Đã chắc chắn đạt (kể cả 0 điểm các môn còn lại).",
                "   ✓ Already guaranteed (even with 0 on the rest)."))
    else:
        print(t(f"   → Cần trung bình {round(need, 2)}/10 trên {remaining} môn còn lại.",
                f"   → Need an average of {round(need, 2)}/10 on the {remaining} remaining."))

def main():
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)

if __name__ == "__main__":
    main()
