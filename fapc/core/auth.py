#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth.py — Đăng nhập FAP qua FE Identity (OAuth2 OIDC), KHÔNG cần máy ảo.

Dành cho sinh viên FPT đăng nhập bằng Google @fpt.edu.vn (khóa 19+).

LỆNH (gói fapc — chạy bằng `fap` sau khi `pip install -e .`):
    fap login            # bắt đầu: mở link, login Google
    fap exchange "<url>" # dán URL redirect (io.identityserver.demo:/...) đổi token
    fap refresh          # làm mới token headless (refresh_token)
    fap fap              # đổi access_token đã lưu -> token FAP (khi bước FAP lỗi)
    fap whoami           # xem token đã lưu

Luồng PKCE (đa số): login -> mở browser + LƯU verifier; đăng nhập Google; trình duyệt báo lỗi
"scheme not registered" (BÌNH THƯỜNG); COPY url; dán vào prompt hoặc `exchange "<url>"`.

CHỈ dùng cho TÀI KHOẢN CỦA CHÍNH BẠN.
"""
import os, sys, json, time, base64, hashlib, secrets, webbrowser, urllib.parse, datetime
import requests
from .api import BASE as FAP_BASE, checksum_login, UA, _vn_now, _is_checksum_error
from . import paths
from ..i18n import t
from .. import config, fmt

# ===== FE Identity (OIDC) — từ /.well-known/openid-configuration =====
ISSUER       = "https://feid.fpt.edu.vn"
DEVICE_EP    = ISSUER + "/connect/deviceauthorization"
AUTHORIZE_EP = ISSUER + "/connect/authorize"
TOKEN_EP     = ISSUER + "/connect/token"
CLIENT_ID    = "fap-mobile-front-end"          # public client (PKCE, không secret)
REDIRECT_URI = "io.identityserver.demo:/oauthredirect"
SCOPE        = "openid email profile offline_access"   # thêm fsp-mobile-front-end/identity-service nếu token bị từ chối

# Đường dẫn state đi qua paths.* để hỗ trợ NHIỀU PROFILE (FAP_PROFILE). Chưa đặt biến ⇒ y HỆT như cũ.
ROOT = paths.ROOT
OUT  = paths.out_dir()
OAUTH_JSON = paths.out("oauth_tokens.json")
TOKEN_JSON = paths.out("token.json")
PKCE_STATE = paths.out(".pkce_state.json")

def _save(path, obj):
    paths.ensure_dir(path)
    # Ghi NGUYÊN TỬ: viết ra .tmp (quyền 0600 ngay từ đầu trên POSIX) rồi os.replace lên đích. Ngắt giữa
    # chừng / đọc-ghi đua nhau KHÔNG làm token.json cụt → mất token (creds() json.load sẽ không thấy file lỗi).
    # Tên tmp phải RIÊNG THEO TIẾN TRÌNH: 3 watcher thường trú (reminders/gradewatch/attendwatch) khởi động
    # cùng lúc sau update.sh và cùng _save() một file — dùng chung "{path}.tmp" thì tiến trình này ghi đè
    # tmp của tiến trình kia giữa chừng → os.replace lên đích một file CỤT.
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
        except OSError:
            with open(tmp, "w", encoding="utf-8") as f:   # filesystem không có mode POSIX -> ghi thường
                json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)                             # thay thế nguyên tử (POSIX & Windows cùng filesystem)
    except BaseException:                                 # noqa: BLE001 — kể cả Ctrl+C: đừng để rác .tmp lại
        try: os.remove(tmp)
        except OSError: pass
        raise
    try: os.chmod(path, 0o600)
    except OSError: pass

_SECRET_KEYS = ("authenkey", "token", "accesstoken", "refresh_token", "id_token",
                "email", "studentname", "fullname", "rollnumber")
def _redact(obj):
    """Che giá trị các khóa nhạy cảm (token/PII) trong dict/list lồng nhau — để dump debug an toàn."""
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if any(s in str(k).lower() for s in _SECRET_KEYS)
                    and isinstance(v, (str, int)) else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj

def _post(url, data, raise_on_neterr=True):
    """POST form, trả (status, json|text). raise_on_neterr=False -> trả (None, lỗi) thay vì SystemExit."""
    try:
        r = requests.post(url, data=data, headers=UA, timeout=25)
    except requests.RequestException as e:
        if raise_on_neterr:
            raise SystemExit(f"Lỗi mạng tới FE Identity: {e}")
        return None, f"net: {e}"
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text

# ---------- đổi access_token -> token FAP ----------
def fap_login_feid(campus, access_token):
    # checksum_login là checksum THEO GIỜ → thử ±1h như data-path (call()/current_semester), chống lệch giờ
    # đầu giờ / đồng hồ máy lệch ~1h (nếu không, login lỗi khó hiểu trong khi `fap grades` vẫn chạy nhờ retry).
    out = (None, None)
    for delta in (0, 1, -1):
        cs = checksum_login(campus, when=_vn_now() + datetime.timedelta(hours=delta))
        url = f"{FAP_BASE}/AuthenticationByFeId?campusCode={campus}&checksum={cs}"
        try:
            r = requests.post(url, json={"token": access_token}, headers=UA, timeout=25)
        except requests.RequestException as e:
            return None, f"Lỗi mạng ({type(e).__name__}) tới AuthenticationByFeId"   # str(e) nhúng url -> tránh lộ
        try:
            out = (r.status_code, r.json())
        except ValueError:
            return r.status_code, r.text
        if not _is_checksum_error(out):                   # không phải lỗi checksum → dùng luôn (kể cả lỗi khác)
            break
    return out

def _do_fap(campus, access_token, log=print):
    http, body = fap_login_feid(campus, access_token)
    code = body.get("code") if isinstance(body, dict) else None
    msg = body.get("message") if isinstance(body, dict) else str(body)[:90]
    log(f"  AuthenticationByFeId -> HTTP {http} code={code} msg={msg}")
    if http != 200:
        log("  ✗ Server FAP không trả 200 — access_token có thể hết hạn (chạy 'refresh') hoặc sai scope."); return None
    raw = body.get("data") if isinstance(body, dict) and "data" in body else body
    if isinstance(raw, list) and raw:
        raw = raw[0]
    tok = None
    if isinstance(raw, str):
        tok = raw
    elif isinstance(raw, dict):
        for k in ("authenKey", "token", "Token", "authenkey", "AuthenKey", "accessToken"):
            if raw.get(k): tok = raw[k]; break
    if not tok:
        # KHÔNG in body thô (có thể chứa token/PII). Chỉ in code+message; lưu file đã CHE bớt.
        log(f"  ✗ Không bóc được token FAP (HTTP {http} code={code} msg={msg}).")
        log("    (đã lưu output/feid_login_raw.json — file này có thể chứa dữ liệu thật, ĐỪNG chia sẻ.)")
        _save(os.path.join(OUT, "feid_login_raw.json"), _redact(body))   # CHỈ ghi khi lỗi, đã che
        return None
    rd = raw if isinstance(raw, dict) else {}
    fap = {"authenkey": tok, "campus": rd.get("campus") or campus,
           "rollnumber": rd.get("rollnumber") or rd.get("rollNumber"),
           "email": rd.get("email"), "fullname": rd.get("studentName") or rd.get("fullname"),
           "obtained_at": int(time.time())}
    _save(TOKEN_JSON, fap)
    log(f"  ✓ Token FAP -> output/token.json  (roll={fap['rollnumber']} campus={fap['campus']})")
    return fap

def _finalize(tok, campus, log=print):
    tok["obtained_at"] = int(time.time())
    _save(OAUTH_JSON, tok)
    # MỘT đối số: `log` có thể là lines.append (đăng nhập từ chat), không phải print đa-đối-số.
    log(f"  ✓ OAuth token (refresh_token = {bool(tok.get('refresh_token'))}"
        f", access hết hạn sau {tok.get('expires_in', '?')} s )")
    log("• Đổi sang token FAP...")
    return _do_fap(campus, tok["access_token"], log)

# ---------- Device flow ----------
def device_start():
    http, j = _post(DEVICE_EP, {"client_id": CLIENT_ID, "scope": SCOPE})
    return (True, j) if http == 200 and isinstance(j, dict) else (False, f"{http}: {str(j)[:160]}")

def device_poll(device_code, interval, expires_in):
    deadline = time.time() + (expires_in or 600)
    while time.time() < deadline:
        time.sleep(max(interval, 1))
        http, j = _post(TOKEN_EP, {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                   "device_code": device_code, "client_id": CLIENT_ID},
                        raise_on_neterr=False)
        if http is None:                 # rớt mạng tạm thời -> chờ vòng sau, đừng giết phiên login
            print("  (mạng chập chờn, đang chờ lại) · (network blip, retrying)")
            continue
        if isinstance(j, dict) and "access_token" in j:
            return j
        err = j.get("error") if isinstance(j, dict) else None
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5; continue
        raise SystemExit(f"Device flow dừng: {err or http} — {j.get('error_description','') if isinstance(j,dict) else j}")
    raise SystemExit("Hết hạn chờ đăng nhập (device flow). Chạy lại 'login'.")

# ---------- Authorization Code + PKCE ----------
def _pkce():
    v = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c

def pkce_start(campus):
    v, c = _pkce(); state = secrets.token_urlsafe(16)
    _save(PKCE_STATE, {"verifier": v, "state": state, "campus": campus})
    url = AUTHORIZE_EP + "?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "scope": SCOPE, "code_challenge": c, "code_challenge_method": "S256", "state": state})
    print("\n========================================================")
    print("  Trình duyệt sẽ mở. ĐĂNG NHẬP GOOGLE @fpt.edu.vn.")
    print("  Link (nếu không tự mở):\n   ", url)
    print("\n  Sau khi login, trình duyệt báo 'scheme ... not ... registered' — ĐÚNG, KHÔNG SAO.")
    print("  COPY URL ở thanh địa chỉ (io.identityserver.demo:/oauthredirect?code=...).")
    print("========================================================\n")
    try: webbrowser.open(url)
    except Exception: pass

def _extract_code(redirected):
    q = urllib.parse.urlparse(redirected.strip().replace("io.identityserver.demo:/", "https://x/")).query
    p = urllib.parse.parse_qs(q)
    if p.get("error"):
        raise SystemExit(f"FE Identity từ chối: {p['error'][0]} — {p.get('error_description',[''])[0]}")
    return (p.get("code") or [None])[0]

def exchange_code(redirected, log=print):
    if not os.path.exists(PKCE_STATE):
        raise SystemExit("Chưa có phiên đăng nhập. Chạy 'login' trước.")
    st = json.load(open(PKCE_STATE, encoding="utf-8"))
    code = _extract_code(redirected)
    if not code:
        raise SystemExit("Không thấy 'code' trong URL bạn dán.")
    http, j = _post(TOKEN_EP, {"grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID, "code_verifier": st["verifier"]})
    if http != 200 or not isinstance(j, dict) or "access_token" not in j:
        raise SystemExit(f"Đổi code lỗi {http}: {str(j)[:300]}\n"
                         "(code chỉ sống ~vài chục giây & dùng 1 lần — chạy lại 'login'.)")
    return _finalize(j, st["campus"], log)

def _truthy(v):
    """'1'/'true'/'yes'/'on' (không phân biệt hoa thường) -> True. Dùng cho cờ ENV, KHÔNG dùng bool()
    vì bool('0') == True — chuỗi '0' trong .env phải hiểu là TẮT."""
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


# ---------- Đăng nhập KHÔNG BÀN PHÍM (cho bot Telegram) ----------
# Vì sao tách riêng: cmd_login() dùng input() + webbrowser -> vô dụng trên VPS và trong bot.
# Ba hàm dưới đây THUẦN-GIAO-TIẾP: nhận vào/trả ra dữ liệu, KHÔNG in, KHÔNG hỏi, KHÔNG mở browser.
#
# BẢO MẬT — mật khẩu KHÔNG BAO GIỜ đi qua bot: đây là OAuth, người dùng đăng nhập trên trang
# Google/FE Identity. Bot chỉ chạm tới (a) link mời đăng nhập, (b) — chỉ ở đường PKCE — MÃ UỶ QUYỀN
# dùng-một-lần sống vài chục giây. Token thật thì ghi thẳng xuống đĩa, không hiện ra chat.

def current_roll():
    """rollNumber trong token.json hiện tại ('' nếu chưa đăng nhập bao giờ)."""
    try:
        with open(TOKEN_JSON, encoding="utf-8") as f:
            return str(json.load(f).get("rollnumber") or "")
    except (OSError, ValueError):
        return ""

_ABSENT = object()      # "file KHÔNG tồn tại" — KHÁC "có file nhưng đọc hỏng" (đừng xoá nhầm bản tốt)

def _snapshot(path):
    """Nội dung file (bytes) | _ABSENT nếu chưa có | None nếu CÓ mà đọc hỏng."""
    if not os.path.exists(path):
        return _ABSENT
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None

def _restore(path, blob):
    """Trả file về đúng bản đã chụp. Trả True nếu CHẮC CHẮN khôi phục xong.
    Ghi NGUYÊN TỬ (tmp + os.replace) như _save: worker thread khôi phục trong khi luồng chính có thể
    đang đọc token.json — ghi đè tại chỗ sẽ để lộ file cụt.
    blob is None = lúc chụp đã đọc hỏng ⇒ KHÔNG đụng vào (thà giữ nguyên còn hơn xoá nhầm)."""
    if blob is None:
        return False
    if blob is _ABSENT:
        try:
            os.remove(path); return True
        except FileNotFoundError:
            return True
        except OSError:
            return False
    tmp = f"{path}.{os.getpid()}.restore"
    try:
        paths.ensure_dir(path)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
        os.replace(tmp, path)
        try: os.chmod(path, 0o600)
        except OSError: pass
        return True
    except OSError:
        try: os.remove(tmp)
        except OSError: pass
        return False

def login_start(campus):
    """Mở một phiên đăng nhập. KHÔNG in, KHÔNG mở browser. Trả dict để caller tự hiển thị:
        {"mode":"device", "url":…, "user_code":…, "device_code":…, "interval":…, "expires_in":…, "campus":…}
        {"mode":"pkce",   "url":…, "campus":…}      # caller phải xin người dùng DÁN URL redirect
    Ưu tiên device flow (mã uỷ quyền KHÔNG đi qua chat); FE Identity từ chối thì mới rơi về PKCE."""
    # Máy CHỈ-ĐỌC (FAP_TOKEN_READONLY) không được tạo/xoay token: nó đang DÙNG CHUNG token của máy
    # chủ (docs/18-roadmap.md §3). Đăng nhập ở đây sẽ mint refresh_token mới và VÔ HIỆU HOÁ bản của
    # máy chủ — đúng thứ mà cờ này sinh ra để ngăn. refresh_tokens() đã chặn; login cũng phải chặn.
    if token_readonly():
        raise PermissionError(
            t("Máy này đặt FAP_TOKEN_READONLY=1 (chỉ đọc, dùng token của máy chủ) nên KHÔNG được "
              "đăng nhập ở đây — làm vậy sẽ vô hiệu hoá token của máy chủ. Hãy /login trên máy chủ.",
              "This host has FAP_TOKEN_READONLY=1 (read-only, shares the owner host's token), so it "
              "must NOT sign in here — that would invalidate the owner host's token. /login there."))
    campus = str(campus or "").strip()
    if not campus:
        raise ValueError("missing campus")
    ok, dev = device_start()
    if ok and isinstance(dev, dict) and dev.get("device_code"):
        return {"mode": "device", "campus": campus,
                "url": dev.get("verification_uri_complete") or dev.get("verification_uri"),
                "user_code": dev.get("user_code") or "",
                "device_code": dev["device_code"],
                "interval": dev.get("interval", 5), "expires_in": dev.get("expires_in", 600)}
    v, c = _pkce(); state = secrets.token_urlsafe(16)
    _save(PKCE_STATE, {"verifier": v, "state": state, "campus": campus})
    url = AUTHORIZE_EP + "?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "scope": SCOPE, "code_challenge": c, "code_challenge_method": "S256", "state": state})
    return {"mode": "pkce", "campus": campus, "url": url}

def _finish(fn, expect_roll):
    """Chạy `fn()` (đường device hoặc PKCE) rồi CHỐT CHẶN ĐỔI TÀI KHOẢN. Trả (ok, thông_điệp).

    Vì sao phải hoàn tác CẢ HAI file: `_finalize` ghi access/refresh_token vào oauth_tokens.json
    TRƯỚC khi `_do_fap` ghi token.json. Chỉ trả lại token.json là chốt chặn VÔ NGHĨA — refresh_token
    của tài khoản lạ còn nằm đó, và lần `refresh_tokens()` kế tiếp (không hề có kiểm tra tài khoản)
    sẽ lặng lẽ dựng lại token của người lạ, đẩy điểm/lịch của họ vào chat của chủ máy.

    Roll RỖNG cũng bị coi là KHÁC: FAP có thể trả `data` là chuỗi trần (xem _do_fap) ⇒ không có
    rollnumber. Không định danh được thì phải TỪ CHỐI, không được tin.

    KHÔNG dùng redirect_stdout: hàm này chạy ở THREAD NỀN, mà redirect_stdout đổi sys.stdout TOÀN
    TIẾN TRÌNH — sẽ nuốt log của vòng lặp bot suốt ~10 phút chờ duyệt. Thay bằng log=callback."""
    lines = []
    before_tok, before_oauth = _snapshot(TOKEN_JSON), _snapshot(OAUTH_JSON)
    try:
        fap = fn(lines.append)
    except SystemExit as e:
        return False, str(e)
    except Exception as e:                                  # noqa: BLE001 — lỗi nào cũng phải thành CHỮ
        return False, f"{type(e).__name__}: {e}"

    def _rollback():
        ok1 = _restore(TOKEN_JSON, before_tok)
        ok2 = _restore(OAUTH_JSON, before_oauth)
        if ok1 and ok2:
            return t("Đã hoàn tác, token cũ giữ nguyên.", "Rolled back; the previous token is untouched.")
        return t("🚨 HOÀN TÁC KHÔNG THÀNH CÔNG — token của tài khoản lạ CÓ THỂ vẫn còn trên máy. "
                 "Hãy đăng nhập lại ngay bằng đúng tài khoản, hoặc xoá output/token.json + "
                 "output/oauth_tokens.json rồi `fap login`.",
                 "🚨 ROLLBACK FAILED — the other account's token may still be on disk. Sign in again "
                 "with the correct account, or delete output/token.json + output/oauth_tokens.json "
                 "and run `fap login`.")

    if not fap:
        tail = [l for l in lines if l][-3:]
        msg = t("Đăng nhập không lấy được token FAP.", "Login did not obtain a FAP token.")
        _rollback()                                          # nửa đường: oauth_tokens.json đã bị ghi
        return False, (msg + "\n" + "\n".join(tail)) if tail else msg
    roll = str(fap.get("rollnumber") or "")
    if expect_roll and roll != expect_roll:
        who = roll or t("(không rõ)", "(unknown)")
        return False, t(f"⛔ Tài khoản KHÁC: vừa đăng nhập bằng {who} nhưng nơi này thuộc về "
                        f"{expect_roll}. ", f"⛔ Different account: signed in as {who} but this "
                        f"profile belongs to {expect_roll}. ") + _rollback()
    return True, t(f"✅ Đăng nhập xong · {roll or '?'} · {fap.get('campus') or '?'}",
                   f"✅ Signed in · {roll or '?'} · {fap.get('campus') or '?'}")

def login_finish_device(session, expect_roll=""):
    """Chờ người dùng bấm duyệt trên trang FE Identity (CHẶN tới vài phút -> caller nên chạy ở thread riêng)."""
    return _finish(lambda log: _finalize(device_poll(session["device_code"], session.get("interval", 5),
                                                     session.get("expires_in", 600)),
                                         session["campus"], log), expect_roll)

def login_finish_code(pasted, expect_roll=""):
    """Đường PKCE: đổi URL redirect người dùng dán thành token."""
    return _finish(lambda log: exchange_code(pasted, log), expect_roll)

def looks_like_redirect(text):
    """THUẦN: tin này có vẻ là URL redirect của luồng đăng nhập không? (bot dùng để XOÁ NGAY tin đó).

    Nhận rộng TAY: chỉ cần thấy scheme redirect là đủ, hoặc là một URL có 'code='/'error='. Thà xoá
    nhầm một tin vô hại còn hơn để lọt một tin có MÃ UỶ QUYỀN nằm lại lịch sử chat. Bản 'error=' cũng
    phải nhận, vì FE Identity trả lỗi về đúng URL đó và người dùng vẫn dán vào chat."""
    s = str(text or "")
    if not s:
        return False
    if REDIRECT_URI.split(":")[0] in s:                # 'io.identityserver.demo' — chắc chắn là redirect
        return True
    return ("http" in s) and ("code=" in s or "error=" in s)


def token_readonly():
    """Máy này có bị cấm refresh không? (FAP_TOKEN_READONLY — xem docs/18-roadmap.md §3)."""
    return _truthy(config.TOKEN_READONLY)


def _refuse_refresh():
    """In banner THẬT TO rồi raise SystemExit. Watcher nuốt SystemExit và chỉ in `e` một dòng, nên phải
    tự in ra stderr ở đây — nếu cờ bị đặt NHẦM trên máy sở hữu token, log vẫn phải hét lên."""
    bar = "!" * 64
    msg = t("Máy này là CLIENT CHỈ-ĐỌC — TỪ CHỐI refresh token.",
            "This machine is a READ-ONLY CLIENT — REFUSING to refresh the token.")
    why = t("FAP_TOKEN_READONLY đang bật. refresh_token bị FE Identity XOAY VÒNG: máy nào refresh trước "
            "thì bản của máy kia thành vô hiệu.",
            "FAP_TOKEN_READONLY is set. FE Identity ROTATES the refresh_token: whichever machine "
            "refreshes first invalidates the other machine's copy.")
    how = t("Refresh chỉ được chạy trên MÁY SỞ HỮU token (VPS). Máy này chỉ chạy lệnh ĐỌC "
            "(status/grades/week/whatif/web/whoami). Nếu ĐÂY chính là máy sở hữu token: bỏ "
            "FAP_TOKEN_READONLY trong .env / unit file rồi khởi động lại — nếu không, token sẽ HẾT HẠN "
            "và mọi watcher im lặng ngừng chạy.",
            "Refresh may only run on the machine that OWNS the token (the VPS). This machine runs "
            "READ-ONLY commands (status/grades/week/whatif/web/whoami). If THIS is the owning machine: "
            "remove FAP_TOKEN_READONLY from .env / the unit file and restart — otherwise the token WILL "
            "EXPIRE and every watcher silently stops.")
    for line in (bar, f"🛑 {msg}{paths.label()}", f"   {why}", f"   {how}", bar):
        print(line, file=sys.stderr, flush=True)
    raise SystemExit(f"🛑 {msg} " + t("(FAP_TOKEN_READONLY=1 — refresh trên máy sở hữu token.)",
                                      "(FAP_TOKEN_READONLY=1 — refresh on the token-owning machine.)"))


def refresh_tokens():
    if token_readonly():                      # CẤM xoay refresh_token của máy khác (docs/18-roadmap.md §3)
        _refuse_refresh()
    if not os.path.exists(OAUTH_JSON):
        raise SystemExit("Chưa có oauth_tokens.json — chạy 'login'.")
    old = json.load(open(OAUTH_JSON, encoding="utf-8")); rt = old.get("refresh_token")
    if not rt:
        raise SystemExit("Không có refresh_token — phải 'login' lại.")
    campus = json.load(open(TOKEN_JSON, encoding="utf-8")).get("campus", "") if os.path.exists(TOKEN_JSON) else ""
    if not campus:
        campus = _ask_campus()
    http, j = _post(TOKEN_EP, {"grant_type": "refresh_token", "refresh_token": rt, "client_id": CLIENT_ID})
    if http != 200 or not isinstance(j, dict) or "access_token" not in j:
        raise SystemExit(f"Refresh lỗi {http}: {str(j)[:200]} — refresh_token hết hạn? Chạy 'login' lại.")
    j.setdefault("refresh_token", rt)
    return _finalize(j, campus)

# ---------- Commands ----------
def _ask_campus():
    """Hỏi CampusCode — KHÔNG mặc định campus nào (đúng cho MỌI sinh viên; chưa biết thì `fap campuses`)."""
    while True:
        c = input("CampusCode (chưa biết? chạy `fap campuses`): ").strip()
        if c:
            return c
        print("  (cần nhập CampusCode)")

def cmd_login():
    campus = _ask_campus()
    print("\n• Thử device flow...")
    ok, dev = device_start()
    if ok:
        print(f"\n  MỞ: {dev.get('verification_uri_complete') or dev.get('verification_uri')}")
        if not dev.get("verification_uri_complete"):
            print("  Mã:", dev.get("user_code"))
        print("• Chờ bạn đăng nhập...")
        return _finalize(device_poll(dev["device_code"], dev.get("interval", 5), dev.get("expires_in")), campus)
    print(f"  (device flow không khả dụng: {dev}) → dùng Authorization Code + PKCE.")
    pkce_start(campus)
    pasted = input("Dán URL redirect (Enter để bỏ qua, đổi sau bằng 'exchange'): ").strip()
    if pasted:
        return exchange_code(pasted)
    print('\n→ Khi có URL, chạy:  fap exchange "<URL redirect>"')

def cmd_fap(campus=None):
    if not os.path.exists(OAUTH_JSON):
        raise SystemExit("Chưa có oauth_tokens.json — chạy 'login'.")
    at = json.load(open(OAUTH_JSON, encoding="utf-8")).get("access_token")
    if not at:
        raise SystemExit("Không có access_token — login lại.")
    campus = campus or _ask_campus()
    print("• Đổi access_token đã lưu -> token FAP...")
    _do_fap(campus, at)

def decode_jwt(tok):
    """THUẦN: payload (phần giữa) của JWT → dict claims. {} nếu không phải JWT/lỗi.
    KHÔNG xác minh chữ ký — CHỈ để hiển thị, tuyệt đối không tin cho quyết định bảo mật."""
    try:
        p = str(tok).split(".")[1]
        return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    except Exception:                              # noqa: BLE001 — token méo → coi như không có claims
        return {}

def token_freshness(claims, now=None):
    """(state, |giây|): 'valid'/'expired'/'unknown' theo claim exp. now=epoch (test inject được)."""
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return ("unknown", 0)
    d = exp - (now if now is not None else time.time())
    return ("valid" if d > 0 else "expired", abs(int(d)))

def _human(s):
    if s < 5400:   return f"{max(1, round(s / 60))} " + t("phút", "min")
    if s < 172800: return f"{round(s / 3600)} " + t("giờ", "h")
    return f"{round(s / 86400)} " + t("ngày", "days")

def cmd_whoami(full=False, as_json=False):
    """Thẻ định danh OFFLINE: decode JWT trong oauth_tokens.json (KHÔNG gọi mạng) + đếm ngược hết hạn."""
    if not (os.path.exists(OAUTH_JSON) or os.path.exists(TOKEN_JSON)):
        print(t("Chưa có token — chạy 'fap login'.", "No token — run 'fap login'.")); return
    oauth = json.load(open(OAUTH_JSON, encoding="utf-8")) if os.path.exists(OAUTH_JSON) else {}
    fap = json.load(open(TOKEN_JSON, encoding="utf-8")) if os.path.exists(TOKEN_JSON) else {}
    claims = decode_jwt(oauth.get("access_token") or oauth.get("id_token") or "")
    state, secs = token_freshness(claims)
    if as_json:
        out = {k: claims.get(k) for k in ("username", "email", "campusCode", "role", "userType", "userId")}
        out["token_state"], out["token_seconds"] = state, secs
        print(json.dumps(out, ensure_ascii=False)); return
    print(fmt.header("🪪", t("Danh tính (offline · từ JWT)", "Identity (offline · from JWT)")))
    rows = [(t("Tài khoản", "User"), claims.get("username") or fap.get("rollnumber")),
            ("Email", claims.get("email")),
            ("Campus", claims.get("campusCode") or fap.get("campus")),
            (t("Vai trò", "Role"), claims.get("role")),
            (t("Loại", "Type"), claims.get("userType")),
            ("User ID", claims.get("userId"))]
    if full:
        rows += [("CCCD/ID", claims.get("citizenCardId")), (t("SĐT", "Phone"), claims.get("phone_number"))]
    for lbl, v in rows:
        if v not in (None, ""):
            print(f"  {lbl:10}: {v}")
    if state == "valid":
        print(t(f"\n🔑 access_token còn hạn ~{_human(secs)}.", f"\n🔑 access_token valid for ~{_human(secs)}."))
    elif state == "expired":
        print(t(f"\n⚠️ access_token đã hết hạn ~{_human(secs)} trước — chạy 'fap refresh'.",
                f"\n⚠️ access_token expired ~{_human(secs)} ago — run 'fap refresh'."))
    if not full:
        print(t("(ẩn CCCD/SĐT — thêm --full để xem; --json cho máy đọc)",
                "(citizenCardId/phone hidden — add --full; --json for scripts)"))

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "login"
    if cmd == "login":      cmd_login()
    elif cmd == "exchange":
        if len(args) < 2: raise SystemExit('Dùng: fap exchange "<URL redirect>"')
        exchange_code(args[1])
    elif cmd == "refresh":  refresh_tokens()
    elif cmd == "fap":      cmd_fap(args[1] if len(args) > 1 else None)
    elif cmd == "whoami":   cmd_whoami()
    else: cmd_login()

if __name__ == "__main__":
    main()
