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
import os, sys, json, time, base64, hashlib, secrets, webbrowser, urllib.parse
import requests
from .api import BASE as FAP_BASE, checksum_login, UA
from ..i18n import t
from .. import fmt

# ===== FE Identity (OIDC) — từ /.well-known/openid-configuration =====
ISSUER       = "https://feid.fpt.edu.vn"
DEVICE_EP    = ISSUER + "/connect/deviceauthorization"
AUTHORIZE_EP = ISSUER + "/connect/authorize"
TOKEN_EP     = ISSUER + "/connect/token"
CLIENT_ID    = "fap-mobile-front-end"          # public client (PKCE, không secret)
REDIRECT_URI = "io.identityserver.demo:/oauthredirect"
SCOPE        = "openid email profile offline_access"   # thêm fsp-mobile-front-end/identity-service nếu token bị từ chối

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT  = os.path.join(ROOT, "output")
OAUTH_JSON = os.path.join(OUT, "oauth_tokens.json")
TOKEN_JSON = os.path.join(OUT, "token.json")
PKCE_STATE = os.path.join(OUT, ".pkce_state.json")

def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Tạo file với quyền 0600 ngay từ đầu (POSIX) — tránh khoảng hở quyền rộng. Windows: bỏ qua.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except OSError:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
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
    url = f"{FAP_BASE}/AuthenticationByFeId?campusCode={campus}&checksum={checksum_login(campus)}"
    try:
        r = requests.post(url, json={"token": access_token}, headers=UA, timeout=25)
    except requests.RequestException as e:
        return None, f"Lỗi mạng ({type(e).__name__}) tới AuthenticationByFeId"   # str(e) nhúng url -> tránh lộ
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text

def _do_fap(campus, access_token):
    http, body = fap_login_feid(campus, access_token)
    code = body.get("code") if isinstance(body, dict) else None
    msg = body.get("message") if isinstance(body, dict) else str(body)[:90]
    print(f"  AuthenticationByFeId -> HTTP {http} code={code} msg={msg}")
    if http != 200:
        print("  ✗ Server FAP không trả 200 — access_token có thể hết hạn (chạy 'refresh') hoặc sai scope."); return None
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
        print(f"  ✗ Không bóc được token FAP (HTTP {http} code={code} msg={msg}).")
        print("    (đã lưu output/feid_login_raw.json — file này có thể chứa dữ liệu thật, ĐỪNG chia sẻ.)")
        _save(os.path.join(OUT, "feid_login_raw.json"), _redact(body))   # CHỈ ghi khi lỗi, đã che
        return None
    rd = raw if isinstance(raw, dict) else {}
    fap = {"authenkey": tok, "campus": rd.get("campus") or campus,
           "rollnumber": rd.get("rollnumber") or rd.get("rollNumber"),
           "email": rd.get("email"), "fullname": rd.get("studentName") or rd.get("fullname"),
           "obtained_at": int(time.time())}
    _save(TOKEN_JSON, fap)
    print(f"  ✓ Token FAP -> output/token.json  (roll={fap['rollnumber']} campus={fap['campus']})")
    return fap

def _finalize(tok, campus):
    tok["obtained_at"] = int(time.time())
    _save(OAUTH_JSON, tok)
    print("  ✓ OAuth token (refresh_token =", bool(tok.get("refresh_token")),
          ", access hết hạn sau", tok.get("expires_in", "?"), "s )")
    print("• Đổi sang token FAP...")
    return _do_fap(campus, tok["access_token"])

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

def exchange_code(redirected):
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
    return _finalize(j, st["campus"])

def refresh_tokens():
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
