#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — cấu hình fap-cli qua biến môi trường / file .env (ở gốc repo).
Không phụ thuộc python-dotenv: tự đọc .env dạng KEY=VALUE.

Việc NẠP .env nằm ở MỘT chỗ duy nhất: `fapc/__init__.py:load_env()` (idempotent, hiểu profile).
Trước đây file này có loader .env RIÊNG chạy sau loader kia và `setdefault` lại TOÀN BỘ .env gốc,
nên profile của bạn bè bị bơm TELEGRAM_CHAT của chủ máy ⇒ rò thông báo. Xem docs/18-roadmap.md §4.
KHÔNG thêm loader thứ hai vào đây nữa.
"""
import os

from . import load_env as _load_env   # `import fapc` đã nạp rồi; gọi lại chỉ để chắc chắn (no-op)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # gốc repo (giữ tên cũ)
_ENV = os.path.join(_ROOT, ".env")                                    # chỉ để tham chiếu/chẩn đoán

_load_env()

# Ngôn ngữ thông báo/log: 'vi' (mặc định) hoặc 'en'
FAP_LANG = os.environ.get("FAP_LANG", "vi")
TZID = "Asia/Ho_Chi_Minh"

# Kênh thông báo (để trống = tắt kênh đó)
TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT       = os.environ.get("TELEGRAM_CHAT")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Google Calendar
GCAL_CALENDAR_ID = os.environ.get("GCAL_CALENDAR_ID", "primary")

# Bot tương tác (interactive bots) — KHÁC với webhook/notify push ở trên.
# Telegram bot dùng lại TELEGRAM_TOKEN + TELEGRAM_CHAT (khóa bot vào chat của bạn).
DISCORD_BOT_TOKEN       = os.environ.get("DISCORD_BOT_TOKEN")        # token bot (≠ webhook URL)
DISCORD_ALLOWED_USER_ID = os.environ.get("DISCORD_ALLOWED_USER_ID")  # chỉ trả lời user này

# Theo dõi điểm danh (watch-attendance): "1"/"true" -> CHỈ báo buổi vắng/muộn (đỡ spam).
WATCH_ABSENT_ONLY = os.environ.get("FAP_WATCH_ABSENT_ONLY")

# Nhắc trước mỗi tiết học (bot tương tác tự đẩy): số PHÚT trước giờ vào lớp. 0/“off” = tắt. Mặc định 30.
REMIND_MINUTES = os.environ.get("FAP_REMIND_MINUTES", "30")

# Tự cập nhật KHI ĐANG CHẠY (bot/watcher thường trú): số PHÚT giữa mỗi lần dò `git pull`.
# 0 = TẮT (mặc định). Khi >0: tiến trình nền tự pull → chạy selftest → nếu PASS thì tự khởi động lại
# để nạp mã mới (bot vẫn có lệnh /update thủ công dù bật hay tắt). Xem fapc/app/selfupdate.py.
AUTOUPDATE_MIN = os.environ.get("FAP_AUTOUPDATE_MIN", "0")

# Nhiều tài khoản trên CÙNG 1 máy: tên profile đang chạy. "" = chế độ 1 tài khoản như cũ.
# Có profile -> trạng thái nằm ở output/profiles/<tên>/ (fapc/core/paths.py) và cấu hình đọc từ
# .env.<tên> ở gốc repo (fapc/__init__.py). Mỗi profile chạy 1 tiến trình/unit riêng.
PROFILE = os.environ.get("FAP_PROFILE", "")

# Máy PHỤ (vd cái PC) dùng CHUNG session với máy chính: "1"/"true" -> CẤM refresh token trên máy này.
# refresh_token XOAY VÒNG — máy nào refresh trước thì bản của máy kia thành vô hiệu; cờ này giữ cho
# CHỈ MỘT nơi được refresh. ĐỪNG đặt trên máy đang chạy watcher/bot (nơi sở hữu việc refresh).
TOKEN_READONLY = os.environ.get("FAP_TOKEN_READONLY")

# Lệnh bot /update (`git pull` + tự khởi động lại) chạy trên checkout DÙNG CHUNG cho mọi profile:
# "1"/"true" -> cho phép. Để trống = CẤM. Chỉ đặt trong unit của CHỦ MÁY, không đặt cho profile khách.
ALLOW_UPDATE = os.environ.get("FAP_ALLOW_UPDATE")
