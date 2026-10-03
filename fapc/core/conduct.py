#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conduct.py — Điểm rèn luyện / phong trào (GetDiemphongtrao).

FPT yêu cầu điểm rèn luyện để xét tốt nghiệp, nhưng app/web không nhắc → dễ quên.
LƯU Ý server: khi tài khoản CHƯA có dữ liệu, FAP trả `code 201` + message vẫn 'Thành công' + data=null,
và `errorMessage` chứa NullReferenceException — KHÔNG phải token hết hạn. Nhưng `code 201` cũng là mã của
lỗi token ('Token invalid') và lỗi CHECKSUM ('Thông tin checksum không chính xác') — nếu coi MỌI 201 là
"chưa có điểm" thì lỗi checksum (đồng hồ máy lệch) bị giấu thành "chưa có điểm" mãi mãi. Vì vậy:
  • message nói token/đăng nhập/checksum       -> lỗi THẬT, để check_auth báo rõ
  • errorMessage là NullReference (kiểu .NET)   -> "chưa có điểm" (degrade êm)
  • 201 khác                                    -> check_auth báo lỗi (không đoán là "chưa có")
⚠️ errorMessage của ca NullReference có thể nhắc chữ 'checksum' (vết stack / chữ ký hàm có tham số
`checksum`) -> CHỈ đọc 'checksum' ở `message`, không đọc ở `errorMessage`.
Cột render generic theo đúng field server trả (chưa xác minh tên field → không bịa cột).
"""
from .api import creds, call, as_list, current_semester, check_auth, _err_code
from ..i18n import t
from .. import fmt

_AUTH_WORDS = ("token", "authen", "đăng nhập", "login", "checksum")      # đọc ở `message`
_NULLREF = ("nullreference", "object reference not set")                  # đọc ở `errorMessage`

def is_no_data(data):
    """THUẦN: True nếu phản hồi là ca "CHƯA có dữ liệu" của GetDiemphongtrao (code 201 + NullReference).
    False cho mọi 201 do token/checksum (message nói rõ) và cho 201 không kèm NullReference."""
    if _err_code(data) != "201":
        return False
    msg = str(data.get("message") or "").lower()
    if any(k in msg for k in _AUTH_WORDS):
        return False                                   # lỗi xác thực/checksum THẬT — không được giấu
    err = str(data.get("errorMessage") or "").lower()
    return any(k in err for k in _NULLREF)

def fetch(token, campus, roll, sem):
    """GetDiemphongtrao → list (rỗng nếu CHƯA có dữ liệu). Raise (SystemExit) khi token hết hạn, checksum
    sai, hoặc 201 lạ — qua check_auth, cùng thông điệp với mọi lệnh khác."""
    http, data = call("GetDiemphongtrao",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll), ("semester", sem)], roll, campus)
    if http not in (401, 403) and is_no_data(data):
        return []                                      # 201 + NullReference → chưa có điểm
    check_auth(http, data)                             # 401/403/token → hết hạn · checksum → lệch giờ · 201 khác
    return as_list(data)

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
