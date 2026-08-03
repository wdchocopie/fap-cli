#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""telegrambot.py — Bot Telegram TƯƠNG TÁC (long-polling, thuần requests, không thêm dep).

    fap telegram-bot         # chạy nền, trả lời /today /grades /whatif ... trong chat của bạn

Bảo mật: CHỈ trả lời chat có id = TELEGRAM_CHAT (bắt buộc đặt trong .env) — tránh lộ dữ liệu
cho người lạ. Lấy TELEGRAM_TOKEN từ @BotFather, TELEGRAM_CHAT = id chat của bạn (xem docs/13).
"""
import os, sys, time
import requests
from .. import config, fmt
from .bot_core import handle, menu_commands
from .reminders import ClassReminder
from .selfupdate import perform_update, restart, maybe_autoupdate, autoupdate_min, owner_checkout
from ..i18n import t

_TIMEOUT = 30   # long-poll: Telegram giữ kết nối tới 30s nếu chưa có update
# Trần MỘT tin của Telegram là 4096 — chừa biên an toàn. Tin dài hơn được CẮT THÀNH NHIỀU MẨU
# (fmt.chunks) rồi gửi lần lượt; KHÔNG cắt cụt bằng [:N] làm mất chữ (vd /grades-detail 5325 ký tự).
_LIMIT = 4000
_GAP   = 0.4    # giây nghỉ giữa 2 mẩu — nhẹ tay với API (số mẩu rất nhỏ: 2–3)

def _update_allowed():
    """/update chạy `git pull` + restart trên CHECKOUT DÙNG CHUNG → phải bật rõ ràng ở máy chủ.
    Đọc config.ALLOW_UPDATE (FAP_ALLOW_UPDATE); config.py có thể chưa khai báo → lùi về env.
    Chạy dưới profile KHÁCH -> luôn CẤM (khách không được động vào checkout dùng chung)."""
    if not owner_checkout():
        return False
    v = getattr(config, "ALLOW_UPDATE", None)
    if v is None:
        v = os.environ.get("FAP_ALLOW_UPDATE")
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")

def _update_off_msg():
    return t("⛔ /update đang TẮT trên máy này. Bật bằng FAP_ALLOW_UPDATE=1 trong .env — chỉ đặt trên "
             "checkout của chủ máy, vì git pull + khởi động lại ảnh hưởng MỌI profile dùng chung mã nguồn.",
             "⛔ /update is DISABLED on this host. Enable it with FAP_ALLOW_UPDATE=1 in .env — owner's "
             "checkout only, since git pull + restart affects EVERY profile sharing this source tree.")

def _api(method):
    return f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"

def _register_menu():
    """Đăng ký danh sách lệnh GỢI Ý — Telegram hiện nút "Menu" ☰ + tự gợi ý khi gõ '/'.
    Không sống-còn: lỗi mạng thì bot vẫn chạy bình thường (chỉ thiếu menu gợi ý)."""
    cmds = [{"command": n, "description": d[:256]} for n, d in menu_commands()]
    cmds.append({"command": "update",                       # lệnh thường-trú (không có ở web/notify)
                 "description": t("Cập nhật code + khởi động lại", "Update code + restart")[:256]})
    try:
        r = requests.post(_api("setMyCommands"), json={"commands": cmds}, timeout=15)
        print("📋 Menu lệnh đã đăng ký (gõ '/' để xem gợi ý)." if r.ok
              else f"  (không đặt được menu: HTTP {r.status_code})")
    except requests.RequestException as e:
        print("  (không đặt được menu lệnh:", e, ")")

def _partial(done, total):
    """Cảnh báo GỬI DỞ: mẩu đầu đã tới nơi nhưng mẩu sau hỏng -> người đọc đang thiếu chữ."""
    if done:
        print(t(f"  ⚠️ mới gửi {done}/{total} mẩu — phần còn lại CHƯA tới nơi.",
                f"  ⚠️ only {done}/{total} chunks sent — the rest did NOT arrive."))
    return False                                     # gửi dở KHÔNG bao giờ tính là thành công

def _send(chat_id, text):
    """Gửi trả lời, cắt thành NHIỀU tin ≤ _LIMIT. True chỉ khi MỌI mẩu đã tới nơi."""
    parts = fmt.chunks(text, _LIMIT)
    for i, part in enumerate(parts):
        if i:
            time.sleep(_GAP)
        try:
            r = requests.post(_api("sendMessage"), json={"chat_id": chat_id, "text": part}, timeout=20)
        except requests.RequestException as e:
            print("  gửi lỗi mạng · network error:", e)
            return _partial(i, len(parts))
        if not r.ok:                                 # HTTP 4xx/5xx không ném — phải tự kiểm
            print(f"  gửi lỗi · send error: HTTP {r.status_code} {str(r.text)[:140]}")
            return _partial(i, len(parts))
    return True

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
    if autoupdate_min():
        print(t(f"🔄 Tự cập nhật khi đang chạy: BẬT mỗi {autoupdate_min()}' (FAP_AUTOUPDATE_MIN).",
                f"🔄 Update-while-running: ON every {autoupdate_min()}m (FAP_AUTOUPDATE_MIN)."))
    offset = None
    last_tick = 0.0
    last_update = 0.0
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
        # Tự cập nhật khi đang chạy (opt-in FAP_AUTOUPDATE_MIN>0): pull → selftest → tự khởi động lại.
        last_update = maybe_autoupdate(last_update, time.time(), log=lambda m: (print(m), _send(allow, m)))
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
            if cmd.lstrip("/!").strip().lower() == "update":    # cập nhật khi đang chạy (chỉ chủ chat)
                if not _update_allowed():           # checkout dùng chung -> phải bật FAP_ALLOW_UPDATE ở máy chủ
                    _send(chat_id, _update_off_msg())
                    continue
                _send(chat_id, t("⏳ Đang cập nhật (git pull + selftest)…", "⏳ Updating (git pull + selftest)…"))
                summary, do_restart = perform_update()
                _send(chat_id, summary)
                if do_restart:
                    restart()                               # thay tiến trình → quay lại với mã mới
                continue
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
