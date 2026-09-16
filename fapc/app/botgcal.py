#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""botgcal.py — CÀI ĐẶT & ĐỒNG BỘ GOOGLE CALENDAR NGAY TRONG CHAT (Telegram/Discord).

Vì sao cần: `fap calendar-auth` cũ mở trình duyệt tại chỗ (run_local_server) ⇒ vô dụng trên VPS,
và mỗi lần muốn đồng bộ phải SSH vào máy chủ. Module này gói:
  • đăng nhập Google bằng LOOPBACK-PASTE (giống /login của FAP): chat nhận 1 link, người dùng đăng
    nhập trên trang Google rồi DÁN URL redirect (chứa mã dùng-một-lần) vào chat; bot XOÁ tin ngay.
  • đồng bộ / dọn lịch chạy nền, trả kết quả về chat.
  • nhiều ĐÍCH (multi-Google): mỗi đích một NHÃN, xem fapc/app/gcal.py.

TOKEN GOOGLE KHÔNG BAO GIỜ ĐƯỢC IN RA CHAT (gcal.gcal_auth_finish chỉ trả câu xác nhận). Mã uỷ quyền
trong URL dán vào cũng chỉ sống vài chục giây và bị xoá ngay khi nhận.
"""
import threading, time

from . import gcal
from ..i18n import t

# Cửa sổ chờ người dùng dán URL redirect. Hết hạn thì phải bắt đầu lại cho sạch (mã Google ngắn hạn).
PASTE_TTL = 600


class GcalAuthSession:
    """Trạng thái MỘT phiên xác thực Google đang dở. Mỗi tiến trình bot giữ 1 phiên: xác thực là việc
    hiếm + phải tuần tự (hai phiên song song sẽ ghi đè .gcal_oauth.json của nhau)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.label = None
        self.started = 0.0
        self.busy = False

    def clear(self):
        with self._lock:
            self.label, self.started, self.busy = None, 0.0, False

    def waiting_paste(self, now=None):
        now = time.time() if now is None else now
        return bool(self.busy and (now - self.started) <= PASTE_TTL)

    def start(self, label):
        """Mở phiên mới. Trả (ok, text). KHÔNG raise ra ngoài — mọi lỗi thành CHỮ cho chat."""
        with self._lock:
            if self.busy and (time.time() - self.started) > PASTE_TTL:   # phiên cũ quá hạn -> tự nhả
                self.label, self.started, self.busy = None, 0.0, False
            if self.busy:
                secs = int(self.started + PASTE_TTL - time.time())
                left = t(f" (còn ~{secs // 60}′{secs % 60:02d})", f" (~{secs // 60}m{secs % 60:02d}s left)") if secs > 0 else ""
                return False, t(f"⏳ Đang có một phiên xác thực Google chạy dở{left} — xong hoặc hết hạn rồi thử lại.",
                                f"⏳ A Google authorization is already in progress{left} — finish it or wait for it to expire.")
            self.busy = True
        try:
            url, label = gcal.gcal_auth_url(label)
        except SystemExit as e:                                          # thiếu credentials.json / chưa add đích / thiếu lib
            self.busy = False
            return False, "⛔ " + str(e)
        except ValueError as e:                                          # nhãn không hợp lệ
            self.busy = False
            return False, "⛔ " + str(e)
        except Exception as e:                                           # noqa: BLE001
            self.busy = False
            return False, t(f"Không mở được phiên xác thực Google: {type(e).__name__}: {e}",
                            f"Could not start Google authorization: {type(e).__name__}: {e}")
        self.label, self.started = label, time.time()
        return True, _auth_text(url, label)


def _auth_text(url, label):
    where = label or t("mặc định", "default")
    return "\n".join([
        t(f"🔗 Cài Google Calendar cho đích '{where}'. Mở link này rồi đăng nhập Google:",
          f"🔗 Set up Google Calendar for '{where}'. Open this link and sign in to Google:"),
        str(url or ""),
        t("Sau khi đăng nhập, trình duyệt sẽ báo “không kết nối được 127.0.0.1” — ĐÚNG rồi, không sao. "
          "Hãy COPY URL trên thanh địa chỉ và DÁN vào đây.",
          "After signing in the browser will say “can't reach 127.0.0.1” — that is EXPECTED. "
          "Copy the URL from the address bar and paste it here."),
        t("⚠️ URL đó chứa mã dùng-một-lần. Bot XOÁ tin của bạn NGAY KHI NHẬN. Nếu bot không đủ quyền xoá, "
          "nó sẽ báo lại — lúc đó bạn TỰ XOÁ tin giúp.",
          "⚠️ That URL carries a single-use code. The bot deletes your message THE MOMENT it arrives. "
          "If the bot lacks permission to delete, it will say so — then please delete it yourself."),
    ])


def finish_paste(session, pasted):
    """Đổi URL người dùng dán -> token Google (đúng nhãn của phiên). Trả (ok, text)."""
    if not session.waiting_paste():
        return False, t("Phiên xác thực Google đã hết hạn — chạy /calendar-auth để bắt đầu lại.",
                        "The Google authorization session expired — run /calendar-auth to start again.")
    label = session.label
    try:
        msg = gcal.gcal_auth_finish(pasted, label)
        ok = True
    except SystemExit as e:
        ok, msg = False, str(e)
    except Exception as e:                                              # noqa: BLE001
        ok, msg = False, f"{type(e).__name__}: {e}"
    session.clear()
    return ok, msg if ok else t("❌ Xác thực Google thất bại.\n", "❌ Google authorization failed.\n") + str(msg)


def finish_paste_text(session, pasted):
    """Bản trả-CHUỖI của finish_paste — để chạy qua run_async (đổi mã Google GỌI MẠNG, không được chặn
    vòng getUpdates của Telegram)."""
    _ok, msg = finish_paste(session, pasted)
    return msg


def run_async(on_done, fn, *args, **kwargs):
    """Chạy `fn(*args, **kwargs)` (đẩy/dọn cả trăm sự kiện có thể mất vài chục giây) ở THREAD NỀN rồi
    gọi on_done(text). Dùng cho Telegram (vòng getUpdates không được chặn); `fn` phải TRẢ CHUỖI và tự
    nuốt lỗi (gcal.sync_text / gcal.prune_text đều vậy). Discord đã có run_in_executor nên gọi trực tiếp."""
    def _worker():
        try:
            txt = fn(*args, **kwargs)
        except Exception as e:                                         # noqa: BLE001 — thread không chết âm thầm
            txt = t(f"Lỗi Calendar: {type(e).__name__}: {e}", f"Calendar error: {type(e).__name__}: {e}")
        try:
            on_done(txt)
        except Exception:                                              # noqa: BLE001
            pass
    th = threading.Thread(target=_worker, name="fap-gcal", daemon=True)
    th.start()
    return th


def parse_sync_args(arg):
    """THUẦN: chuỗi tham số /calendar-sync|prune -> (label, prune, yes, force).
    Từ khoá: 'prune'|'dọn', 'yes'|'có', 'force'|'ép'. Token còn lại = NHÃN đích."""
    label, prune, yes, force = "", False, False, False
    for tok in str(arg or "").split():
        low = tok.lower()
        if low in ("prune", "dọn", "don"):
            prune = True
        elif low in ("yes", "có", "co", "--yes"):
            yes = True
        elif low in ("force", "ép", "ep", "--force"):
            force = True
        elif not label:
            label = tok
    return label, prune, yes, force
