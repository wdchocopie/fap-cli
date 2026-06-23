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
WHATIF_STEPS = (5, 6, 7, 8, 9, 10)        # dải mốc dùng chung CLI + bot (tránh lệch 5–10 vs 6–10)

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
