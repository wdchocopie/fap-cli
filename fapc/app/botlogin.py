#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""botlogin.py — ĐĂNG NHẬP FAP NGAY TRONG CHAT (không cần SSH vào máy chủ).

Vì sao cần: `fap login` dùng `input()` + mở trình duyệt ⇒ vô dụng trên VPS. Khi token hết hạn,
trước đây phải SSH vào server mới đăng nhập lại được. Với module này chỉ cần gõ `/login` trong chat.

MẬT KHẨU KHÔNG BAO GIỜ ĐI QUA BOT. Đây là OAuth (FE Identity / Google): bạn đăng nhập trên trang
của Google, bot không thấy và không lưu mật khẩu. Bot chỉ chạm tới:
  • device flow  — CHỈ một link mời đăng nhập. Mã uỷ quyền KHÔNG hề đi qua chat. (đường ƯU TIÊN)
  • PKCE (dự phòng, khi FE Identity từ chối device flow) — bạn phải DÁN URL redirect vào chat; URL
    đó chứa MÃ UỶ QUYỀN dùng-một-lần, sống vài chục giây. Caller PHẢI xoá tin nhắn đó ngay
    (`looks_like_redirect` ở core/auth.py giúp nhận diện) — xem telegrambot._handle_login_paste.

Chốt an toàn (đều nằm ở core/auth.py):
  • đổi nhầm tài khoản  -> hoàn tác token.json về bản cũ, từ chối (quan trọng khi chạy nhiều profile)
  • token KHÔNG bao giờ được in ra chat — chỉ báo roll + campus
"""
import threading, time

from ..core import auth
from ..i18n import t

# Cửa sổ chờ người dùng dán URL redirect (đường PKCE) — hết hạn thì phải /login lại cho sạch,
# vì mã uỷ quyền của FE Identity vốn chỉ sống vài chục giây.
PASTE_TTL = 600


class LoginSession:
    """Trạng thái MỘT phiên đăng nhập đang dở. Mỗi tiến trình bot chỉ giữ 1 phiên (đăng nhập là
    việc hiếm + phải tuần tự; hai phiên song song sẽ ghi đè .pkce_state.json của nhau)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.data = None            # dict do auth.login_start trả về
        self.started = 0.0
        self.busy = False           # đang chờ device_poll ở thread nền

    def clear(self):
        with self._lock:
            self.data, self.started, self.busy = None, 0.0, False

    def waiting_paste(self, now=None):
        """Đang ở đường PKCE và còn trong hạn chờ dán URL?"""
        now = time.time() if now is None else now
        d = self.data
        return bool(d and d.get("mode") == "pkce" and (now - self.started) <= PASTE_TTL)

    def start(self, campus):
        """Mở phiên mới. Trả (ok, text, mode). KHÔNG raise ra ngoài — mọi lỗi thành CHỮ cho chat."""
        with self._lock:
            # Phiên PKCE quá hạn chờ dán thì coi như bỏ -> tự nhả, nếu không một lần /login dở dang
            # sẽ khoá luôn việc đăng nhập lại (đúng lúc người dùng cần nhất).
            if self.busy and self.data and self.data.get("mode") == "pkce" \
                    and (time.time() - self.started) > PASTE_TTL:
                self.data, self.started, self.busy = None, 0.0, False
            if self.busy:
                left = ""
                if self.data and self.started:
                    secs = int(self.started + (self.data.get("expires_in") or PASTE_TTL) - time.time())
                    if secs > 0:
                        left = t(f" (còn ~{secs // 60}′{secs % 60:02d})", f" (~{secs // 60}m{secs % 60:02d}s left)")
                return False, t(f"⏳ Đang có một phiên đăng nhập chạy dở{left} — xong hoặc hết hạn rồi /login lại.",
                                f"⏳ A sign-in is already in progress{left} — finish it or wait for it to expire."), None
            self.busy = True
        try:
            data = auth.login_start(campus)
        except PermissionError as e:                            # máy chỉ-đọc (FAP_TOKEN_READONLY)
            self.busy = False
            return False, "⛔ " + str(e), None
        except ValueError:
            self.busy = False
            return False, _campus_help(), None
        except Exception as e:                                  # noqa: BLE001 — lỗi mạng/FE Identity
            self.busy = False
            return False, t(f"Không mở được phiên đăng nhập: {type(e).__name__}: {e}",
                            f"Could not start sign-in: {type(e).__name__}: {e}"), None
        self.data, self.started = data, time.time()
        # GIỮ cờ bận cho CẢ HAI đường. Đường PKCE cũng phải giữ: .pkce_state.json chỉ có MỘT chỗ, nên
        # /login lần hai sẽ ghi đè `verifier` của phiên đang chờ ⇒ URL người dùng dán vào sau đó
        # không đổi được nữa (verifier không khớp code). Hết PASTE_TTL thì start() tự nhả (xem dưới).
        return True, (_device_text(data) if data["mode"] == "device" else _pkce_text(data)), data["mode"]


def _campus_help():
    """Thiếu campus (lần đầu đăng nhập, chưa có token.json). Người dùng CHỈ có chat — không chạy được
    `fap campuses` — nên phải đưa luôn danh sách vào tin nhắn. GetAllActiveCampus là endpoint CÔNG KHAI
    (không cần token), đúng thứ cần lúc chưa đăng nhập."""
    head = t("Thiếu mã campus. Gõ ví dụ:  /login APHL", "Missing campus code. Send e.g.:  /login APHL")
    try:
        from ..core.extras import campuses_text
        return head + "\n\n" + campuses_text()
    except Exception:                                       # noqa: BLE001 — mạng hỏng thì vẫn phải trả lời
        return head + "\n" + t("(không tải được danh sách campus — thử lại sau)",
                               "(could not load the campus list — try again later)")


def _device_text(d):
    code = d.get("user_code")
    lines = [t("🔐 Đăng nhập FAP — mở link này rồi đăng nhập Google @fpt.edu.vn:",
               "🔐 FAP sign-in — open this link and sign in with your @fpt.edu.vn Google account:"),
             str(d.get("url") or "")]
    if code:
        lines.append(t(f"Mã xác nhận: {code}", f"Confirmation code: {code}"))
    lines.append(t("Xong là bot tự báo — không cần dán gì cả. Mật khẩu bạn nhập trên trang Google, "
                   "bot không thấy.",
                   "The bot reports back automatically — nothing to paste. You type your password on "
                   "Google's page; the bot never sees it."))
    return "\n".join(lines)


def _pkce_text(d):
    return "\n".join([
        t("🔐 Đăng nhập FAP — mở link này rồi đăng nhập Google @fpt.edu.vn:",
          "🔐 FAP sign-in — open this link and sign in with your @fpt.edu.vn Google account:"),
        str(d.get("url") or ""),
        t("Sau khi đăng nhập, trình duyệt sẽ báo lỗi kiểu “scheme … not registered” — ĐÚNG rồi, "
          "không sao. Hãy COPY URL trên thanh địa chỉ và DÁN vào đây.",
          "After signing in the browser will fail with “scheme … not registered” — that is EXPECTED. "
          "Copy the URL from the address bar and paste it here."),
        t("⚠️ URL đó chứa mã dùng-một-lần. Bot XOÁ tin của bạn NGAY KHI NHẬN (trước cả khi đổi mã). "
          "Nếu bot không đủ quyền xoá, nó sẽ báo lại — lúc đó bạn TỰ XOÁ tin giúp.",
          "⚠️ That URL carries a single-use code. The bot deletes your message THE MOMENT it arrives "
          "(before exchanging it). If the bot lacks permission to delete, it will say so — then please "
          "delete the message yourself."),
    ])


def finish_device(session, on_done):
    """Chờ duyệt ở THREAD NỀN (device_poll chặn tới ~10 phút) rồi gọi on_done(text).
    Không bao giờ để sót cờ `busy`, kể cả khi thread chết giữa chừng."""
    d = session.data

    def _worker():
        try:
            ok, msg = auth.login_finish_device(d, auth.current_roll())
        except Exception as e:                                  # noqa: BLE001 — thread không được chết âm thầm
            ok, msg = False, f"{type(e).__name__}: {e}"
        finally:
            session.clear()
        try:
            on_done(msg if ok else t("❌ Đăng nhập thất bại.\n", "❌ Sign-in failed.\n") + msg)
        except Exception:                                       # noqa: BLE001 — gửi hỏng không được làm chết bot
            pass

    th = threading.Thread(target=_worker, name="fap-login", daemon=True)
    th.start()
    return th


def finish_paste(session, pasted):
    """Đường PKCE: đổi URL người dùng vừa dán -> token. Trả (ok, text)."""
    if not session.waiting_paste():
        return False, t("Phiên đăng nhập đã hết hạn — gõ /login để bắt đầu lại.",
                        "The sign-in session expired — send /login to start again.")
    try:
        ok, msg = auth.login_finish_code(pasted, auth.current_roll())
    except Exception as e:                                      # noqa: BLE001
        ok, msg = False, f"{type(e).__name__}: {e}"
    session.clear()
    return ok, msg if ok else t("❌ Đăng nhập thất bại.\n", "❌ Sign-in failed.\n") + msg


def default_campus():
    """Campus suy từ token.json hiện có ('' nếu chưa từng đăng nhập) — để `/login` khỏi phải gõ campus
    khi chỉ là đăng nhập LẠI."""
    try:
        import json
        with open(auth.TOKEN_JSON, encoding="utf-8") as f:
            return str(json.load(f).get("campus") or "")
    except (OSError, ValueError):
        return ""
