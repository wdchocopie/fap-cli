#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — cấu hình fap-cli qua biến môi trường / file .env (ở gốc repo).
Không phụ thuộc python-dotenv: tự đọc .env dạng KEY=VALUE.
"""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV = os.path.join(_ROOT, ".env")

def _load_env():
    if not os.path.exists(_ENV):
        return
    for line in open(_ENV, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))   # bỏ nháy bao quanh

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
