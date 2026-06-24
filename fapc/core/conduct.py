#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conduct.py — Điểm rèn luyện / phong trào (GetDiemphongtrao).

FPT yêu cầu điểm rèn luyện để xét tốt nghiệp, nhưng app/web không nhắc → dễ quên.
LƯU Ý server: khi tài khoản CHƯA có dữ liệu, FAP trả `code 201` + NullReferenceException
(message vẫn 'Thành công', data=null) — KHÔNG phải token hết hạn. Vì vậy ở đây phân biệt:
chỉ raise khi message báo token/đăng nhập; còn lại coi như 'chưa có điểm' (degrade êm).
Cột render generic theo đúng field server trả (chưa xác minh tên field → không bịa cột).
"""
from .api import creds, call, as_list, current_semester, _err_code, _EXPIRED_MSG
from ..i18n import t
from .. import fmt

def fetch(token, campus, roll, sem):
    """GetDiemphongtrao → list (rỗng nếu CHƯA có dữ liệu / server 201-null). Raise CHỈ khi token hết hạn."""
    http, data = call("GetDiemphongtrao",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll), ("semester", sem)], roll, campus)
    if http in (401, 403):
        raise SystemExit(_EXPIRED_MSG)
    low = str(data.get("message") or "").lower() if isinstance(data, dict) else ""
    if _err_code(data) == "201" and any(k in low for k in ("token", "authen", "đăng nhập", "login")):
        raise SystemExit(_EXPIRED_MSG)                 # token thật hết hạn
    return as_list(data)                               # 201/null/NullReference → [] (chưa có điểm)

def conduct_text(token, campus, roll, sem):
    rows = fetch(token, campus, roll, sem)
    if not rows:
        return t("🎖️ Chưa có điểm rèn luyện/phong trào kỳ này (FAP chưa cập nhật hoặc bạn chưa tham gia).",
                 "🎖️ No conduct/movement points this term yet (FAP hasn't posted them, or none earned).")
    out = [fmt.header("🎖️", t(f"Điểm rèn luyện · {sem}", f"Conduct points · {sem}"),
                      t(f"{len(rows)} mục", f"{len(rows)} items"))]
    out.append(fmt.table(rows))                        # generic — đúng field server, không bịa cột
    return "\n".join(out)

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    print(conduct_text(token, campus, roll, sem))
