#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attendance.py — điểm danh (GetStudentAttendances) + cảnh báo nguy cơ cấm thi."""
from .api import creds, call, as_list, current_semester, check_auth
from ..i18n import t

# FPT: vắng > 20% tổng buổi -> cấm thi. Proxy theo % chuyên cần hiện tại.
BAN_THRESHOLD = 80   # < 80% chuyên cần = nguy cơ

def fetch(token, campus, roll, sem):
    http, data = call("GetStudentAttendances",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _pct(r):
    """% chuyên cần. None nếu CHƯA có dữ liệu (rỗng/None) — KHÁC với 0% thật."""
    v = r.get("attendance")
    if v in (None, ""):
        return None
    try: return float(v)
    except (TypeError, ValueError): return None

def _at_risk(r):
    """True nếu môn có nguy cơ cấm thi. Môn CHƯA có dữ liệu (None) -> KHÔNG tính nguy cơ."""
    p = _pct(r)
    return p is not None and p < BAN_THRESHOLD

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = fetch(token, campus, roll, sem)
    print(t(f"== Điểm danh kỳ {sem} ==", f"== Attendance {sem} =="))
    print(f"{'Môn/Subject':12} {'Có mặt/Present':>13} {'Tổng/Total':>10} {'%':>6}")
    for r in rows:
        print(f"{r.get('subjectCode',''):12} {str(r.get('numberOfTakenAttendances','')):>13} "
              f"{str(r.get('numberOfAttendances','')):>10} {str(r.get('attendance','')):>6}")

def banrisk():
    """In các môn nguy cơ cấm thi. Trả exit code 2 nếu có nguy cơ (cho cron/CI)."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = fetch(token, campus, roll, sem)
    at_risk = [r for r in rows if _at_risk(r)]
    if not at_risk:
        print(t("✓ Không môn nào nguy cơ cấm thi (chuyên cần ≥ 80%).",
                "✓ No exam-ban risk (attendance ≥ 80%).")); return 0
    print(t("⚠️  NGUY CƠ CẤM THI (chuyên cần < 80%):", "⚠️  EXAM-BAN RISK (attendance < 80%):"))
    for r in at_risk:
        print(f"   {r.get('subjectCode','')}: {r.get('attendance','')}%")
    return 2
