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
from . import botlogin
from ..core.auth import looks_like_redirect
from .selfupdate import perform_update, restart, maybe_autoupdate, autoupdate_min, owner_checkout
from ..i18n import t

_TIMEOUT = 30   # long-poll: Telegram giữ kết nối tới 30s nếu chưa có update
# Trần MỘT tin của Telegram là 4096 — chừa biên an toàn. Tin dài hơn được CẮT THÀNH NHIỀU MẨU
# (fmt.chunks) rồi gửi lần lượt; KHÔNG cắt cụt bằng [:N] làm mất chữ (vd /grades-detail 5325 ký tự).
_LIMIT = 4000
_GAP   = 0.4    # giây nghỉ giữa 2 mẩu — nhẹ tay với API (số mẩu rất nhỏ: 2–3)
_CB_MAX = 64    # callback_data của Telegram tối đa 64 BYTE (utf-8) — dài hơn là API từ chối cả tin
_MENU_MAX  = 12 # số nút trên bảng menu — nhiều hơn thì bàn phím dài lê thê, che hết màn hình
_MENU_COLS = 3  # Telegram cho tối đa 8 nút/hàng; 3 nút/hàng vừa mắt trên điện thoại

# MỘT phiên đăng nhập cho cả tiến trình: đăng nhập là việc hiếm và phải tuần tự (2 phiên song song
# sẽ ghi đè .pkce_state.json của nhau). Xem fapc/app/botlogin.py.
_LOGIN = botlogin.LoginSession()

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
    cmds.append({"command": "menu",                         # lệnh thường-trú (không có ở web/notify)
                 "description": t("Bảng nút bấm nhanh", "Quick button panel")[:256]})
    cmds.append({"command": "login",                         # đăng nhập FAP ngay trong chat
                 "description": t("Đăng nhập lại FAP (token hết hạn)", "Re-login to FAP (token expired)")[:256]})
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

def _cb_data(name):
    """callback_data tối đa 64 BYTE utf-8 (không phải ký tự) — cắt theo BYTE cho chắc.
    Tên lệnh dài nhất hiện nay là 'exam_countdown' (14) nên thực tế không bao giờ chạm trần."""
    raw = str(name).encode("utf-8")[:_CB_MAX]
    return raw.decode("utf-8", "ignore")

def _keyboard(buttons):
    """[[(nhãn, data), ...], ...] -> reply_markup của Telegram. Rỗng/None -> None (gửi như cũ)."""
    rows = [[{"text": str(label), "callback_data": _cb_data(data)} for label, data in row]
            for row in (buttons or []) if row]
    return {"inline_keyboard": rows} if rows else None

def _menu_buttons():
    """Bàn phím nút bấm, DẪN XUẤT từ bot_core.menu_commands() -> không thể lệch COMMAND_INFO.
    Nhãn = tên lệnh có dấu '/' cho dễ nhận; callback_data = chính tên lệnh (handle() tự chuẩn hoá
    '_' -> '-'). Cắt còn _MENU_MAX nút, xếp _MENU_COLS nút/hàng."""
    cells = [("/" + name.replace("_", "-"), name) for name, _ in menu_commands()[:_MENU_MAX]]
    return [cells[i:i + _MENU_COLS] for i in range(0, len(cells), _MENU_COLS)]

def _menu_text():
    return handle("help") + "\n\n" + t("👇 Chạm nút bên dưới để chạy lệnh (khỏi gõ tay).",
                                       "👇 Tap a button below to run a command (no typing).")

def _send(chat_id, text, buttons=None):
    """Gửi trả lời, cắt thành NHIỀU tin ≤ _LIMIT. True chỉ khi MỌI mẩu đã tới nơi.
    buttons: [[(nhãn, data), ...], ...] -> gắn inline_keyboard vào mẩu CUỐI (nút phải nằm dưới
    ĐOẠN CUỐI người đọc nhìn thấy; gắn vào mẩu đầu thì bàn phím bị các mẩu sau đẩy trôi lên)."""
    parts = fmt.chunks(text, _LIMIT)
    markup = _keyboard(buttons)
    for i, part in enumerate(parts):
        if i:
            time.sleep(_GAP)
        body = {"chat_id": chat_id, "text": part}
        if markup and i == len(parts) - 1:
            body["reply_markup"] = markup
        try:
            r = requests.post(_api("sendMessage"), json=body, timeout=20)
        except requests.RequestException as e:
            print("  gửi lỗi mạng · network error:", e)
            return _partial(i, len(parts))
        if not r.ok:                                 # HTTP 4xx/5xx không ném — phải tự kiểm
            print(f"  gửi lỗi · send error: HTTP {r.status_code} {str(r.text)[:140]}")
            return _partial(i, len(parts))
    return True

def _answer_callback(cb_id, text=None):
    """BẮT BUỘC sau mỗi lần bấm nút: không gọi thì Telegram để nút quay vòng vòng ~30s trên máy
    người bấm. Gọi NGAY (trước khi chạy lệnh) vì lệnh có thể mất vài giây chờ mạng FAP."""
    if not cb_id:
        return
    body = {"callback_query_id": cb_id}
    if text:
        body["text"] = str(text)[:200]
    try:
        requests.post(_api("answerCallbackQuery"), json=body, timeout=15)
    except requests.RequestException as e:
        print("  trả lời nút lỗi · answerCallbackQuery error:", e)

def _delete_message(chat_id, message_id):
    """Xoá 1 tin trong chat. Dùng cho tin chứa URL redirect (có MÃ UỶ QUYỀN dùng-một-lần):
    mã đã đổi xong thì không có lý do gì để nó nằm lại lịch sử chat. Lỗi thì bỏ qua — bot có thể
    thiếu quyền xoá tin của người dùng trong group; khi đó phải NÓI cho người dùng tự xoá."""
    if not message_id:
        return False
    try:
        r = requests.post(_api("deleteMessage"),
                          json={"chat_id": chat_id, "message_id": message_id}, timeout=15)
        return bool(r.ok)
    except requests.RequestException:
        return False

def _login_start(chat_id, arg):
    """/login [CAMPUS] — mở phiên đăng nhập FAP ngay trong chat (không cần SSH vào máy chủ)."""
    campus = (arg or "").strip() or botlogin.default_campus()
    ok, text, mode = _LOGIN.start(campus)
    _send(chat_id, text)
    if ok and mode == "device":
        # device_poll CHẶN tới ~10 phút -> chạy thread nền, KHÔNG được giữ vòng getUpdates
        # (giữ thì bot đứng hình và, quan trọng hơn, NHẮC TIẾT cũng ngừng chạy).
        botlogin.finish_device(_LOGIN, lambda msg: _send(chat_id, msg))

def _login_paste(chat_id, text, message_id):
    """Người dùng dán URL redirect (đường PKCE). Xoá tin NGAY rồi mới đổi mã."""
    deleted = _delete_message(chat_id, message_id)
    ok, msg = botlogin.finish_paste(_LOGIN, text)
    if not deleted:
        msg += "\n" + t("⚠️ Bot không xoá được tin chứa link — bạn TỰ XOÁ giúp (nó có mã đăng nhập).",
                        "⚠️ The bot could not delete your link message — please delete it yourself "
                        "(it carries a sign-in code).")
    _send(chat_id, msg)

def _dispatch(chat_id, cmd, arg=None):
    """Chạy MỘT lệnh rồi gửi trả lời — dùng chung cho tin GÕ TAY và cho NÚT BẤM.
    Người gọi đã kiểm quyền (chỉ chat chủ) trước khi vào đây."""
    key = (cmd or "").strip().lstrip("/!").lower().replace("_", "-")
    if key == "update":                         # cập nhật khi đang chạy (chỉ chủ chat)
        if not _update_allowed():               # checkout dùng chung -> phải bật FAP_ALLOW_UPDATE ở máy chủ
            _send(chat_id, _update_off_msg())
            return
        _send(chat_id, t("⏳ Đang cập nhật (git pull + selftest)…", "⏳ Updating (git pull + selftest)…"))
        summary, do_restart = perform_update()
        _send(chat_id, summary)
        if do_restart:
            restart()                           # thay tiến trình → quay lại với mã mới
        return
    if key == "login":                           # đăng nhập FAP ngay trong chat (khỏi SSH vào máy chủ)
        _login_start(chat_id, arg)
        return
    if key in ("", "menu", "start", "help"):     # trang trợ giúp = luôn kèm bàn phím nút bấm
        _send(chat_id, _menu_text(), _menu_buttons())
        return
    try:
        reply = handle(cmd, arg)
    except SystemExit as e:
        reply = str(e)
    except Exception as e:                       # noqa: BLE001 — bot không được chết vì 1 lệnh
        reply = f"Lỗi · error: {e}"
    print(f"  > {key[:40]}  ->  {len(reply)} ký tự")
    _send(chat_id, reply)

def run():
    if not config.TELEGRAM_TOKEN:
        raise SystemExit("Thiếu TELEGRAM_TOKEN trong .env (lấy từ @BotFather).")
    allow = str(config.TELEGRAM_CHAT) if config.TELEGRAM_CHAT else None
    if not allow:
        raise SystemExit("Thiếu TELEGRAM_CHAT trong .env — bắt buộc, để bot CHỈ trả lời chat của bạn "
                         "(không thì người lạ cũng truy vấn được dữ liệu của bạn). Xem docs/13-notify.md.")
    print(f"🤖 Bot Telegram đang chạy (chỉ chat {allow}). Ctrl+C để dừng.")
    print(t("🔘 Gõ /menu trong chat để hiện bảng NÚT BẤM (khỏi phải gõ lệnh).",
            "🔘 Send /menu in the chat for the tap-to-run BUTTON panel."))
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
            cb = upd.get("callback_query")
            if cb:                                 # NGƯỜI DÙNG BẤM NÚT (inline_keyboard)
                cb_chat = str(((cb.get("message") or {}).get("chat") or {}).get("id"))
                data = (cb.get("data") or "").strip()
                # Trả lời nút TRƯỚC (bắt buộc, kể cả khi từ chối) rồi mới chạy lệnh cho đỡ quay vòng.
                _answer_callback(cb.get("id"))
                if cb_chat != allow or not data:
                    continue                       # im lặng y như tin nhắn ngoài allowlist
                print(f"  🔘 nút · button: {data[:40]}")
                _dispatch(cb_chat, data)
                continue
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = str(msg.get("chat", {}).get("id"))
            text = (msg.get("text") or "").strip()
            if chat_id != allow:
                continue                       # im lặng với chat ngoài allowlist (không xác nhận bot sống)
            if not text:
                continue
            # XOÁ TRƯỚC, XÉT SAU. Bất kỳ tin nào TRÔNG GIỐNG URL redirect đều đi lối này, KHÔNG cần
            # đang có phiên: nếu gài thêm điều kiện "đang chờ dán" thì khi phiên đã hết hạn (hoặc bot
            # vừa restart vì auto-update) tin chứa MÃ UỶ QUYỀN sẽ rơi xuống _dispatch — không được xoá,
            # lại còn bị "Lệnh không rõ: <cả URL>" ném ngược vào chat ⇒ mã nằm lại lịch sử chat 2 lần.
            if looks_like_redirect(text):
                _login_paste(chat_id, text, msg.get("message_id"))
                continue
            # split(None, 1): giữ NGUYÊN phần còn lại làm tham số. split() thường sẽ cắt mất chữ ở
            # tham số nhiều từ ('/news học bổng' -> 'học'), trong khi CLI/notify/slash đều giữ đủ.
            parts = text.split(None, 1)
            cmd, arg = parts[0], (parts[1].strip() or None if len(parts) > 1 else None)
            _dispatch(chat_id, cmd, arg)

def main():
    try:
        run()
    except KeyboardInterrupt:
        print("\nĐã dừng bot.")
        sys.exit(0)

if __name__ == "__main__":
    main()
