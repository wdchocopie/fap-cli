#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paths.py — MỘT nơi duy nhất quyết định file trạng thái nằm ở đâu (hỗ trợ NHIỀU PROFILE).

    FAP_PROFILE chưa đặt   ->  <gốc repo>/output/…                      (y HỆT trước đây)
    FAP_PROFILE=alice      ->  <gốc repo>/output/profiles/alice/…

Nhờ vậy nhiều tài khoản FAP chạy trên CÙNG 1 máy mà token / baseline / cache KHÔNG đè nhau.
Không đặt biến ⇒ mọi đường dẫn resolve ra ĐÚNG chuỗi như cũ ⇒ máy đang chạy không cần migrate.

THUẦN + không phụ thuộc: đọc thẳng os.environ (KHÔNG import config) để tránh vòng import —
`fapc/__init__.py` đã nạp .env trước mọi submodule nên biến môi trường luôn sẵn sàng.

LƯU Ý cho người gọi: các module giữ hằng ở cấp module (vd `STATE = paths.out("grade_state.json")`)
nên profile được chốt lúc IMPORT. Đổi FAP_PROFILE giữa chừng trong 1 tiến trình sẽ KHÔNG có tác dụng —
đúng như thiết kế: mỗi profile chạy 1 tiến trình riêng.
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tên profile chỉ cho phép chữ/số/._- : chặn '..' và dấu phân cách đường dẫn (không cho thoát ra ngoài output/).
_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def profile():
    """Tên profile đã LÀM SẠCH ('' nếu không dùng profile). Tên không hợp lệ -> '' (rơi về mặc định,
    KHÔNG raise: một biến môi trường gõ nhầm không được làm chết mọi lệnh)."""
    name = (os.environ.get("FAP_PROFILE") or "").strip()
    if not name or name == "." or name == ".." or not _SAFE.match(name):
        return ""
    return name


def out_dir():
    """Thư mục trạng thái của profile hiện tại. Không profile -> <repo>/output (như cũ)."""
    p = profile()
    return os.path.join(ROOT, "output", "profiles", p) if p else os.path.join(ROOT, "output")


def out(*parts):
    """Đường dẫn 1 file/thư mục trạng thái, vd paths.out('token.json') hoặc paths.out('api', 'x.json')."""
    return os.path.join(out_dir(), *parts)


def ensure_dir(path):
    """Tạo thư mục CHA của `path` nếu chưa có. Trả lại chính `path` (tiện nối chuỗi khi ghi file)."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    return path


def label():
    """Nhãn ngắn để in ra log/thông báo: '' khi không profile, ' [alice]' khi có."""
    p = profile()
    return f" [{p}]" if p else ""
