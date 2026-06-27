#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""telegrambot.py — Bot Telegram TƯƠNG TÁC (long-polling, thuần requests, không thêm dep).

    fap telegram-bot         # chạy nền, trả lời /today /grades /whatif ... trong chat của bạn

Bảo mật: CHỈ trả lời chat có id = TELEGRAM_CHAT (bắt buộc đặt trong .env) — tránh lộ dữ liệu
cho người lạ. Lấy TELEGRAM_TOKEN từ @BotFather, TELEGRAM_CHAT = id chat của bạn (xem docs/13).
"""
import sys, time
import requests
from .. import config
from .bot_core import handle, menu_commands
from .reminders import ClassReminder

_TIMEOUT = 30   # long-poll: Telegram giữ kết nối tới 30s nếu chưa có update

def _api(method):
    return f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"

def _register_menu():
    """Đăng ký danh sách lệnh GỢI Ý — Telegram hiện nút "Menu" ☰ + tự gợi ý khi gõ '/'.
    Không sống-còn: lỗi mạng thì bot vẫn chạy bình thường (chỉ thiếu menu gợi ý)."""
    cmds = [{"command": n, "description": d[:256]} for n, d in menu_commands()]
    try:
        r = requests.post(_api("setMyCommands"), json={"commands": cmds}, timeout=15)
        print("📋 Menu lệnh đã đăng ký (gõ '/' để xem gợi ý)." if r.ok
              else f"  (không đặt được menu: HTTP {r.status_code})")
    except requests.RequestException as e:
        print("  (không đặt được menu lệnh:", e, ")")

def _send(chat_id, text):
    try:
        r = requests.post(_api("sendMessage"), json={"chat_id": chat_id, "text": text[:4000]}, timeout=20)
        if not r.ok:                                 # HTTP 4xx/5xx không ném — phải tự kiểm
            print(f"  gửi lỗi · send error: HTTP {r.status_code} {str(r.text)[:140]}")
    except requests.RequestException as e:
        print("  gửi lỗi mạng · network error:", e)

def run():
    if not config.TELEGRAM_TOKEN:
        raise SystemExit("Thiếu TELEGRAM_TOKEN trong .env (lấy từ @BotFather).")
    allow = str(config.TELEGRAM_CHAT) if config.TELEGRAM_CHAT else None
    if not allow:
        raise SystemExit("Thiếu TELEGRAM_CHAT trong .env — bắt buộc, để bot CHỈ trả lời chat của bạn "
                         "(không thì người lạ cũng truy vấn được dữ liệu của bạn). Xem docs/13-notify.md.")
    print(f"🤖 Bot Telegram đang chạy (chỉ chat {allow}). Ctrl+C để dừng.")
    _register_menu()
    reminder = ClassReminder()
    print(f"⏰ Nhắc trước mỗi tiết {reminder.lead}' (vào chat {allow})." if reminder.enabled()
          else "⏰ Nhắc lịch: TẮT (đặt FAP_REMIND_MINUTES>0 trong .env để bật).")
    offset = None
    last_tick = 0.0
    # Bỏ qua tồn đọng cũ lúc khởi động · skip backlog on startup
    try:
        r = requests.get(_api("getUpdates"), params={"timeout": 0}, timeout=15).json()
        if r.get("result"):
            offset = r["result"][-1]["update_id"] + 1
    except requests.RequestException:
        pass

    while True:
        # NHẮC TIẾT chạy ĐỘC LẬP với getUpdates: đặt ở ĐẦU vòng → không bị bỏ lượt khi Telegram lỗi
        # mạng / trả not-ok (những nhánh `continue` bên dưới). Throttle ~20s cho nhẹ.
        if reminder.enabled() and time.time() - last_tick >= 20:
            last_tick = time.time()
            try:
                for txt in reminder.tick():
                    print(f"  ⏰ nhắc tiết  ->  {len(txt)} ký tự")
                    _send(allow, txt)
            except Exception as e:                       # noqa: BLE001 — nhắc lỗi không được làm chết bot
                print("  nhắc lỗi · reminder error:", e)
        try:
            r = requests.get(_api("getUpdates"), params={"timeout": _TIMEOUT, "offset": offset},
                             timeout=_TIMEOUT + 10).json()
        except requests.RequestException as e:
            print("  mạng lỗi · network error:", e); time.sleep(5); continue
        if not r.get("ok"):
            print("  Telegram:", str(r)[:200]); time.sleep(5); continue
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = str(msg.get("chat", {}).get("id"))
            text = (msg.get("text") or "").strip()
            if chat_id != allow:
                continue                       # im lặng với chat ngoài allowlist (không xác nhận bot sống)
            if not text:
                continue
            parts = text.split()
            cmd, arg = parts[0], (parts[1] if len(parts) > 1 else None)
            try:
                reply = handle(cmd, arg)
            except SystemExit as e:
                reply = str(e)
            except Exception as e:                       # noqa: BLE001 — bot không được chết vì 1 lệnh
                reply = f"Lỗi · error: {e}"
            print(f"  > {text[:40]}  ->  {len(reply)} ký tự")
            _send(chat_id, reply)

def main():
    try:
        run()
    except KeyboardInterrupt:
        print("\nĐã dừng bot.")
        sys.exit(0)

if __name__ == "__main__":
    main()
