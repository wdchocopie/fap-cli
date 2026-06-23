#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api.py — thư viện chung cho fap-cli (gói fapc).

Cung cấp:
  creds()                         -> (token, campus, roll) đọc từ output/token.json
  checksum_auth(a, b)             -> getCheckSumAuthenicated (HMAC-SHA1)
  checksum_login(campus)          -> getCheckSumLogin
  call(endpoint, params, ...)     -> GET, trả (http_status, json_hoặc_text); bắt lỗi mạng
  current_semester(...)           -> học kỳ hiện tại (env FAP_SEMESTER > auto-detect > mặc định)

Cơ chế (reverse từ app com.fuct, React Native + Hermes):
  Authen   = token đăng nhập (lấy qua: fap login / fap refresh)
  checksum = base64(HMAC_SHA1(SECRET, <message> + 'DD/MM/YYYY HH:00')).replace('=','%3d').replace(' ','+')

⚠️ SECRET/LOGIN_PREFIX dưới đây trích từ APK CÔNG KHAI của app — đây là dự án KHÔNG chính thức,
   chỉ dùng cho TÀI KHOẢN CỦA CHÍNH BẠN. Đừng dùng để giả mạo / truy cập dữ liệu người khác.
"""
import os, sys, json, sqlite3, hmac, hashlib, base64, datetime, time, urllib.parse
import requests

# In tiếng Việt/emoji không lỗi trên console Windows (cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SECRET       = "n4ASsbkaW6ddhIkF0ipiNmxIMnzix3lRe62s2mTobKnk2enA2eoZQMybF3geLcN5Uw0lR3NXzbgd9mQH00qsNwbCHZW0fOM08tAFfcS0AAzPFuctlJeMVuqxuGN2fNRV"
LOGIN_PREFIX = "TlKiA0340pY6Hkio4kaTLFMvxK7GIOlr6xqV7mVAI4bRch7sfjOOx7FnIpV1dwvveH0j5xsRzKlRD6sqNOAy0G492cmQB5xlIQNFiXyS28pXVXTN7Emy77vHNas2kLpEMYFAP"
BASE         = "https://api.fpt.edu.vn/fap/api/MyFAP"


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_JSON = os.path.join(_ROOT, "output", "token.json")
DB = os.path.join(_ROOT, "device-data", "com.fuct", "databases", "RKStorage")   # legacy (pull_token.py)
UA = {"User-Agent": "okhttp/4.9.2"}


# ---------- thông tin đăng nhập ----------
def creds():
    """Trả (token, campus, roll). Ưu tiên output/token.json (do `fap login` / `fap refresh` tạo),
    fallback RKStorage chỉ cho hướng legacy máy ảo (legacy/pull_token.py)."""
    token = campus = roll = None
    if os.path.exists(TOKEN_JSON):
        t = json.load(open(TOKEN_JSON, encoding="utf-8"))
        token, campus, roll = t.get("authenkey"), t.get("campus"), t.get("rollnumber")
    elif os.path.exists(DB):
        con = sqlite3.connect(DB); c = con.cursor()
        def g(k):
            c.execute("SELECT value FROM catalystLocalStorage WHERE key=?", (k,)); r = c.fetchone(); return r[0] if r else None
        token, campus, roll = g("authenkey"), g("campus"), g("rollnumber"); con.close()
    if not token:
        raise SystemExit("Chưa có token. Đăng nhập trước:  fap login")
    if not campus or not roll:
        raise SystemExit("Thiếu campus/rollNumber trong token.json — đăng nhập lại: fap login")
    return token, campus, roll


# ---------- checksum ----------
def _vn_now():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)

# ---------- học kỳ mặc định (suy theo NGÀY, đúng cho MỌI sinh viên/mọi kỳ — không hardcode) ----------
def default_semester(when=None):
    """Tên học kỳ FPT đoán theo ngày VN: Spring (T1–4) / Summer (T5–8) / Fall (T9–12) + năm.
    Dùng làm fallback khi GetSemester lỗi — KHÔNG cố định 1 kỳ (để người dùng kỳ nào cũng chạy được)."""
    d = when or _vn_now()
    season = "Spring" if d.month <= 4 else ("Summer" if d.month <= 8 else "Fall")
    return f"{season}{d.year}"

def _sign(msg, secret=SECRET):
    d = hmac.new(secret.encode(), str(msg).encode(), hashlib.sha1).digest()
    return base64.b64encode(d).decode().replace("=", "%3d").replace(" ", "+")

def checksum_auth(a, b, secret=SECRET, when=None):
    """getCheckSumAuthenicated(a, b): HMAC_SHA1(SECRET, a + 'MYFAP' + b + 'DD/MM/YYYY HH:00')."""
    when = when or _vn_now()
    return _sign(f"{a}MYFAP{b}" + when.strftime("%d/%m/%Y %H") + ":00", secret)

def checksum_login(campus, secret=SECRET, when=None):
    """getCheckSumLogin(campus): HMAC_SHA1(SECRET, LOGIN_PREFIX + campus + 'DD/MM/YYYY HH:00')."""
    when = when or _vn_now()
    return _sign(LOGIN_PREFIX + campus + when.strftime("%d/%m/%Y %H") + ":00", secret)

def checksum(roll, campus, secret=SECRET, when=None):
    """Mặc định cho hầu hết endpoint dữ liệu: checksum_auth(rollNumber, campusCode)."""
    return checksum_auth(roll, campus, secret, when)


# ---------- gọi API ----------
# Cache GET trong-bộ-nhớ (opt-in: FAP_CACHE_MIN phút, mặc định 0 = tắt). Giúp web server / status
# bớt gọi lại endpoint giống nhau; chỉ cache phản hồi HTTP 200; tự hết hạn -> không lo dữ liệu cũ qua phiên.
_CACHE = {}
def _cache_ttl():
    try: return float(os.environ.get("FAP_CACHE_MIN", "0")) * 60
    except (TypeError, ValueError): return 0.0

def _err_code(data):
    return str(data.get("code")) if isinstance(data, dict) else None

def _is_checksum_error(out):
    """True nếu phản hồi là lỗi CHECKSUM (HTTP 200 + code 201 + message nhắc 'checksum').
    Đã probe THẬT: xảy ra khi giờ checksum lệch giờ server — hay gặp ngay ranh giới đầu giờ."""
    http, data = out
    return http == 200 and _err_code(data) == "201" \
        and "checksum" in str(data.get("message", "")).lower()

def call(endpoint, params, roll, campus, base=BASE, secret=SECRET, timeout=25, checksum_value=None):
    """params: list[(key,value)]. checksum_value: override; None = checksum_auth(roll,campus);
    False = không gửi checksum (vd GetSemesterMark). Trả (http_status|None, json|text|thông-báo-lỗi).
    Tự thử lại ±1h nếu lỗi checksum (chỉ khi dùng checksum mặc định) — chống lệch giờ đầu giờ."""
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params)
    ttl = _cache_ttl()
    key = f"{endpoint}?{qs}" if ttl > 0 else None        # bỏ checksum khỏi key (đổi theo giờ)
    if key is not None:
        hit = _CACHE.get(key)
        if hit and hit[0] > time.time():
            return hit[1]

    def _fetch(cs):
        url = f"{base}/{endpoint}?{qs}" if cs is False else f"{base}/{endpoint}?{qs}&checksum={cs}"
        try:
            # allow_redirects=False: token (Authen) nằm trong query string -> KHÔNG theo 30x sang host khác.
            r = requests.get(url, timeout=timeout, headers=UA, allow_redirects=False)
        except requests.RequestException as e:
            # KHÔNG nội suy str(e): chuỗi requests/urllib3 nhúng NGUYÊN url (chứa Authen=<token>) -> lộ token.
            return None, f"Lỗi mạng ({type(e).__name__}) khi gọi {endpoint}"
        try:
            return (r.status_code, r.json())
        except ValueError:
            return (r.status_code, r.text)

    if checksum_value is False:
        out = _fetch(False)
    elif checksum_value is not None:
        out = _fetch(checksum_value)                     # override (vd login/news) -> không tự retry
    else:
        out = _fetch(checksum(roll, campus, secret))
        if _is_checksum_error(out):
            # Lỗi checksum = giờ tính != giờ server. Thử lại giờ KỀ tính theo ĐỒNG HỒ LÚC retry:
            #   delta 0  -> ranh giới đầu giờ do trễ mạng (hay gặp nhất; đồng hồ đã nhích sang giờ mới)
            #   delta +1 -> đồng hồ máy CHẬM ~1h · -1 -> đồng hồ máy NHANH ~1h
            for delta in (0, 1, -1):
                out = _fetch(checksum(roll, campus, secret, when=_vn_now() + datetime.timedelta(hours=delta)))
                if not _is_checksum_error(out):
                    break

    # chỉ cache phản hồi THẬT-SỰ thành công (không cache lỗi auth/checksum dù HTTP vẫn 200)
    if key is not None and out[0] == 200 and _err_code(out[1]) != "201":
        _CACHE[key] = (time.time() + ttl, out)
    return out

def unwrap(resp):
    """Bóc lớp {code,message,data}. Trả phần data (có thể là list/dict/scalar)."""
    if isinstance(resp, dict) and "data" in resp:
        return resp.get("data")
    return resp

def as_list(resp):
    """unwrap rồi đảm bảo trả về list (rỗng nếu lỗi/không phải list)."""
    d = unwrap(resp)
    return d if isinstance(d, list) else []

_EXPIRED_MSG = "⚠️ Token FAP có thể đã hết hạn — chạy:  fap refresh  (rồi thử lại)."

def check_auth(http, data):
    """Raise thông điệp RÕ khi phản hồi báo lỗi XÁC THỰC, thay vì để fetch_* trả [] im lặng
    (người dùng tưởng 'hết môn/hết điểm').
    Đã PROBE THẬT (tests/live_smoke.py --probe-auth) — FAP trả HTTP 200 + code='201' cho:
      • token hết hạn/sai  -> message 'Token invalid'
      • checksum sai        -> message 'Thông tin checksum không chính xác'
    Phân biệt bằng message (call() đã tự thử lại ±1h cho checksum trước khi tới đây)."""
    if http in (401, 403):
        raise SystemExit(_EXPIRED_MSG)
    if _err_code(data) == "201":
        low = str(data.get("message") or "").lower()
        if "token" in low or "authen" in low or "đăng nhập" in low or "login" in low:
            raise SystemExit(_EXPIRED_MSG)
        if "checksum" in low:                  # call() đã retry ±1h mà vẫn lỗi -> đồng hồ máy lệch nhiều
            raise SystemExit("⚠️ Lỗi checksum — đồng hồ máy bạn có thể lệch giờ Việt Nam (UTC+7). "
                             "Chỉnh lại giờ hệ thống rồi thử lại.")
        raise SystemExit(f"⚠️ FAP từ chối yêu cầu (code 201): {data.get('message')}")


# ---------- học kỳ ----------
def current_semester(token, campus, roll):
    """Trả tên học kỳ: env FAP_SEMESTER > tự dò qua GetSemester (theo ngày) > đoán theo ngày (default_semester).
    HỢP ĐỒNG: LUÔN trả 1 chuỗi (không raise) — dashboard/bot_core/webui gộp nhiều mục, dựa vào điều này."""
    if os.environ.get("FAP_SEMESTER"):
        return os.environ["FAP_SEMESTER"]
    try:
        # checksum_login là override -> call() KHÔNG tự retry; tự thử ±1h tại đây (lệch giờ đầu giờ).
        out = None
        for delta in (0, 1, -1):
            when = _vn_now() + datetime.timedelta(hours=delta)
            out = call("GetSemester", [("campusCode", campus), ("Authen", token)],
                       roll, campus, checksum_value=checksum_login(campus, when=when))
            if not _is_checksum_error(out):
                break
        if _err_code(out[1]) == "201":          # token hết hạn / checksum vẫn lỗi -> cảnh báo, đừng nuốt im
            print(f"⚠️ Không tự dò được học kỳ (GetSemester lỗi auth/checksum) — "
                  f"tạm dùng {default_semester()!r}. Đặt FAP_SEMESTER trong .env nếu sai.", file=sys.stderr)
            return default_semester()
        sems = as_list(out[1])
        now = _vn_now().replace(tzinfo=None)
        def _in_range(s):
            # parse AN TOÀN từng mục: 1 kỳ có ngày lỗi KHÔNG được làm hỏng cả việc dò (FAP trả ~28 kỳ).
            try:
                return (datetime.datetime.fromisoformat(str(s.get("startDate")))
                        <= now <= datetime.datetime.fromisoformat(str(s.get("endDate"))))
            except (ValueError, TypeError):
                return False
        cur = [s for s in sems if _in_range(s)]
        if cur:
            return cur[-1].get("semesterName") or default_semester()
    except Exception:
        pass
    return default_semester()
