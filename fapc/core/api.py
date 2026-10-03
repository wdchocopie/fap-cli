#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api.py — thư viện chung cho fap-cli (gói fapc).

Cung cấp:
  creds()                         -> (token, campus, roll) đọc từ output/token.json
  checksum_auth(a, b)             -> getCheckSumAuthenicated (HMAC-SHA1)
  checksum_login(campus)          -> getCheckSumLogin
  call(endpoint, params, ...)     -> GET, trả (http_status, json_hoặc_text); bắt lỗi mạng
                                     (FAP_API_VERSION=v2 -> rẽ sang apiv2.call_v2 — opt-in, thử nghiệm)
  check_auth / is_session_expired -> nhận ra token hết hạn (v1 code 201 + thân kiểu v2 code 401/'Unauthorized')
  classify_drift(...)             -> THUẦN: phản hồi trông như v1 đã dời route (30x/410/404 không-JSON)?
  select_semester(sems, now)      -> THUẦN: quy tắc chọn kỳ của màn hình chính myFAP 2.0.5
  current_semester(...)           -> học kỳ hiện tại (env FAP_SEMESTER > auto-detect > mặc định)

Cơ chế (reverse từ app com.fuct, React Native + Hermes):
  Authen   = token đăng nhập (lấy qua: fap login / fap refresh)
  checksum = base64(HMAC_SHA1(SECRET, <message> + 'DD/MM/YYYY HH:00')).replace('=','%3d').replace(' ','+')

⚠️ SECRET/LOGIN_PREFIX dưới đây trích từ APK CÔNG KHAI của app — đây là dự án KHÔNG chính thức,
   chỉ dùng cho TÀI KHOẢN CỦA CHÍNH BẠN. Đừng dùng để giả mạo / truy cập dữ liệu người khác.
"""
import os, sys, json, sqlite3, hmac, hashlib, base64, datetime, time, urllib.parse
import requests
from . import paths

# In tiếng Việt/emoji không lỗi trên console Windows (cp1252) — CẢ stderr: banner cảnh báo
# (vd FAP_TOKEN_READONLY ở auth._refuse_refresh) in ra stderr, không sửa thì thành \uXXXX khó đọc.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SECRET       = "n4ASsbkaW6ddhIkF0ipiNmxIMnzix3lRe62s2mTobKnk2enA2eoZQMybF3geLcN5Uw0lR3NXzbgd9mQH00qsNwbCHZW0fOM08tAFfcS0AAzPFuctlJeMVuqxuGN2fNRV"
LOGIN_PREFIX = "TlKiA0340pY6Hkio4kaTLFMvxK7GIOlr6xqV7mVAI4bRch7sfjOOx7FnIpV1dwvveH0j5xsRzKlRD6sqNOAy0G492cmQB5xlIQNFiXyS28pXVXTN7Emy77vHNas2kLpEMYFAP"
BASE         = "https://api.fpt.edu.vn/fap/api/MyFAP"


_ROOT = paths.ROOT
TOKEN_JSON = paths.out("token.json")            # theo FAP_PROFILE; chưa đặt biến ⇒ <repo>/output/token.json
DB = os.path.join(_ROOT, "device-data", "com.fuct", "databases", "RKStorage")   # legacy (pull_token.py)
                                                # ↑ KHÔNG per-profile: dump máy ảo cũ, không phải state profile
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
        raise SystemExit("Chưa có token. Đăng nhập trước:  fap login  (hoặc gõ /login trong chat bot).\n"
                         "No token yet. Sign in first:  fap login  (or send /login to the bot).")
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

# ---------- cảnh báo SỚM: v1 có thể đã "dời nhà" (API v2) — THỤ ĐỘNG, KHÔNG thêm request nào ----------
# Chỉ tín hiệu MỨC ĐƯỜNG DẪN (route): 30x (call() chạy allow_redirects=False), 410, và 404 mà thân KHÔNG
# phải JSON (trang HTML/rỗng của web server = route không tồn tại). 404 CÓ thân JSON là lỗi DỮ LIỆU của
# chính endpoint (đo trên dump thật: GeFeeByRoll -> 404 + {"Message": …}) -> KHÔNG phải drift.
_REDIRECT_CODES = (301, 302, 303, 307, 308)
# Endpoint ĐÃ 404 + HTML từ trước (đo trên dump thật: GetSemesterMark, GetVersion; GetCourseOfSemester theo
# docs/03, thân chưa rõ) -> 404 kiểu đó là "bình thường", đừng báo động giả mỗi lần `fap extract`/`fap courses`.
# Chỉ miễn lý do 404; 30x/410 trên chính các endpoint này VẪN là tín hiệu.
_KNOWN_404 = frozenset({"GetSemesterMark", "GetVersion", "GetCourseOfSemester"})
_DRIFT_WARNED = {"done": False}       # 1 lần / process (dict để test reset được, khỏi `global`)

def _looks_json(body, content_type=""):
    """THUẦN: thân phản hồi có phải JSON? body = chuỗi thô, HOẶC object call() đã parse (dict/list/số ⇒ JSON)."""
    if body is None:
        return False
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if not isinstance(body, str):
        return True                                   # r.json() đã thành công
    s = body.strip()
    if not s or "html" in str(content_type or "").lower():
        return False
    try:
        json.loads(s)
        return True
    except ValueError:
        return False

def classify_drift(http_status, body_text, content_type=""):
    """THUẦN: phản hồi v1 trông như FAP đã DỜI/TẮT route? -> None, hoặc khoá lý do ngắn:
      'redirect'  — HTTP 301/302/303/307/308 (không theo redirect: token nằm trong query)
      'gone'      — HTTP 410
      'not_found' — HTTP 404 mà thân KHÔNG phải JSON (HTML hoặc rỗng)
    404 có thân JSON, 200/201/401/403/5xx, lỗi mạng (None) -> None."""
    try:
        code = int(http_status)
    except (TypeError, ValueError):
        return None
    if code in _REDIRECT_CODES:
        return "redirect"
    if code == 410:
        return "gone"
    if code == 404 and not _looks_json(body_text, content_type):
        return "not_found"
    return None

_DRIFT_REASON = {"redirect": ("chuyển hướng 30x", "30x redirect"),
                 "gone": ("410 Gone", "410 Gone"),
                 "not_found": ("404 không phải JSON", "non-JSON 404")}

def _warn_drift(endpoint, http_status, reason):
    """In ĐÚNG 1 gợi ý song ngữ ra stderr cho tín hiệu drift ĐẦU TIÊN của process. Trả True nếu đã in.
    CHỈ in tên endpoint + mã HTTP — KHÔNG BAO GIỜ in URL (chứa Authen=<token>) hay thân phản hồi."""
    if not reason or _DRIFT_WARNED["done"]:
        return False
    if reason == "not_found" and endpoint in _KNOWN_404:
        return False
    _DRIFT_WARNED["done"] = True
    vi, en = _DRIFT_REASON.get(reason, (reason, reason))
    try:                                                 # chỉ là chẩn đoán: stderr hỏng/đóng KHÔNG được làm hỏng call()
        print(f"⚠️ FAP trả {endpoint} → HTTP {http_status} ({vi}): có thể FAP đã chuyển sang API v2 / tắt API v1. "
              f"Xem docs/21-api-v2.md và FAP_API_VERSION. (Chỉ báo 1 lần.)\n"
              f"⚠️ FAP answered {endpoint} with HTTP {http_status} ({en}): FAP may have moved to API v2 / turned v1 off. "
              f"See docs/21-api-v2.md and FAP_API_VERSION. (Shown once.)", file=sys.stderr)
    except (OSError, ValueError):
        pass
    return True

def _is_checksum_error(out):
    """True nếu phản hồi là lỗi CHECKSUM (HTTP 200 + code 201 + message nhắc 'checksum').
    Đã probe THẬT: xảy ra khi giờ checksum lệch giờ server — hay gặp ngay ranh giới đầu giờ."""
    http, data = out
    return http == 200 and _err_code(data) == "201" \
        and "checksum" in str(data.get("message", "")).lower()

def call(endpoint, params, roll, campus, base=BASE, secret=SECRET, timeout=25, checksum_value=None):
    """params: list[(key,value)]. checksum_value: override; None = checksum_auth(roll,campus);
    False = không gửi checksum (vd GetSemesterMark). Trả (http_status|None, json|text|thông-báo-lỗi).
    Tự thử lại ±1h nếu lỗi checksum (chỉ khi dùng checksum mặc định) — chống lệch giờ đầu giờ.
    API v2 (opt-in FAP_API_VERSION=v2, docs/21-api-v2.md): CHỈ rẽ nhánh ở đầu hàm sang apiv2.call_v2 (cùng
    hợp đồng trả về; base/secret/checksum_value bỏ qua). Token.json lệch phiên bản -> SystemExit 'fap refresh'."""
    from . import apiv2                                  # import trễ: apiv2 import ngược module này
    if endpoint not in apiv2.V1_ONLY:                    # GetAllActiveCampus: luôn v1, không token (fap campuses)
        ver = apiv2.api_version()
        apiv2.check_session_version(ver)
        if ver == "v2":
            return apiv2.call_v2(endpoint, params, roll, campus)
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
            out = (r.status_code, r.json())
        except ValueError:
            out = (r.status_code, r.text)
        # Cảnh báo sớm v1 dời nhà: soi CHÍNH phản hồi vừa nhận (0 request thêm). getattr: response giả trong test
        # có thể không có .headers.
        try:
            ctype = (getattr(r, "headers", None) or {}).get("Content-Type", "")
        except Exception:                                # noqa: BLE001 — headers lạ không được làm hỏng call()
            ctype = ""
        _warn_drift(endpoint, out[0], classify_drift(out[0], out[1], ctype))
        return out

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

def call_login_retry(endpoint, params, roll, campus):
    """call() với checksum_login (override) + TỰ THỬ ±1h. Endpoint ký bằng checksum_login (GetSemester,
    GetSubjets) là override -> call() KHÔNG tự retry; gom logic retry ở đây để mọi nơi dùng chung.
    API v2: chữ ký theo epoch giây (không theo giờ) -> gọi ĐÚNG 1 lần, không vòng ±1h."""
    from . import apiv2
    if endpoint not in apiv2.V1_ONLY and apiv2.api_version() == "v2":
        return call(endpoint, params, roll, campus)
    out = (None, None)
    for delta in (0, 1, -1):
        out = call(endpoint, params, roll, campus,
                   checksum_value=checksum_login(campus, when=_vn_now() + datetime.timedelta(hours=delta)))
        if not _is_checksum_error(out):
            break
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

# Nhắc CẢ HAI đường: người dùng chat không chạy được lệnh shell, người dùng CLI không có bot.
_EXPIRED_MSG = ("⚠️ Token FAP có thể đã hết hạn — chạy:  fap refresh  (hoặc gõ /login trong chat bot), rồi thử lại.\n"
                "⚠️ The FAP token may have expired — run:  fap refresh  (or send /login to the bot), then retry.")

def _is_v2_session_error(data):
    """THUẦN: thân lỗi phiên KIỂU API v2 — đúng `_isSessionExpired` của myFAP 2.0.5 (đọc từ bytecode):
    `code == '401'` (app so LỎNG `==` nên số 401 cũng tính) HOẶC `errorMessage === 'Unauthorized'`
    (ở đây nới thêm: bỏ khoảng trắng + không phân biệt hoa/thường). Bọc trong HTTP 200 vẫn nhận ra."""
    if not isinstance(data, dict):
        return False
    code = data.get("code")
    if not isinstance(code, bool) and (str(code).strip() == "401"
                                       or (isinstance(code, (int, float)) and code == 401)):
        return True
    em = data.get("errorMessage")
    return isinstance(em, str) and em.strip().lower() == "unauthorized"

def _mentions_login(data):
    """Message của code '201' nhắc token/đăng nhập (đã PROBE THẬT: 'Token invalid')."""
    low = str(data.get("message") or "").lower() if isinstance(data, dict) else ""
    return "token" in low or "authen" in low or "đăng nhập" in low or "login" in low

def is_session_expired(http, data):
    """THUẦN: True nếu phản hồi báo PHIÊN/token hết hạn — đúng những ca check_auth raise _EXPIRED_MSG
    (HTTP 401/403 · thân kiểu v2 · code '201' + message nhắc token). Cho nơi KHÔNG muốn raise (watcher
    trả None, conduct…) dùng chung một luật. HTTP 500 KHÔNG tính: app chính thức đăng xuất khi gặp 500,
    nhưng với fap-cli làm vậy = vòng refresh vô ích mỗi lần server trục trặc."""
    if http in (401, 403) or _is_v2_session_error(data):
        return True
    return _err_code(data) == "201" and _mentions_login(data)

def check_auth(http, data):
    """Raise thông điệp RÕ khi phản hồi báo lỗi XÁC THỰC, thay vì để fetch_* trả [] im lặng
    (người dùng tưởng 'hết môn/hết điểm').
    Đã PROBE THẬT (tests/live_smoke.py --probe-auth) — FAP trả HTTP 200 + code='201' cho:
      • token hết hạn/sai  -> message 'Token invalid'
      • checksum sai        -> message 'Thông tin checksum không chính xác'
    Phân biệt bằng message (call() đã tự thử lại ±1h cho checksum trước khi tới đây).
    Thêm (chuẩn bị API v2): thân `code '401'` / `errorMessage 'Unauthorized'` -> cũng là hết phiên.
    HTTP 500 -> KHÔNG coi là hết phiên (xem is_session_expired)."""
    if http in (401, 403) or _is_v2_session_error(data):
        raise SystemExit(_EXPIRED_MSG)
    if _err_code(data) == "201":
        low = str(data.get("message") or "").lower()
        if _mentions_login(data):
            raise SystemExit(_EXPIRED_MSG)
        if "checksum" in low:                  # call() đã retry ±1h mà vẫn lỗi -> đồng hồ máy lệch nhiều
            raise SystemExit("⚠️ Lỗi checksum — đồng hồ máy bạn có thể lệch giờ Việt Nam (UTC+7). "
                             "Chỉnh lại giờ hệ thống rồi thử lại.")
        raise SystemExit(f"⚠️ FAP từ chối yêu cầu (code 201): {data.get('message')}")


# ---------- học kỳ ----------
_SEM_DATE_FMTS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")     # cùng thứ tự với schedule.parse_date

def _sem_dt(v):
    """THUẦN: mốc ngày của GetSemester -> datetime NAIVE (giờ VN), None nếu không đọc được.
    Shape thật: '2026-09-07T00:00:00' (28/28 kỳ trên dump thật đều 00:00:00). Nhận thêm 'YYYY-MM-DD',
    'MM/DD/YYYY', 'DD/MM/YYYY' (-> 00:00). Có múi giờ thì bỏ tzinfo, giữ giờ-đồng-hồ như server gửi."""
    s = str(v if v is not None else "").strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        pass
    day = s.split("T")[0].split(" ")[0]
    for f in _SEM_DATE_FMTS:
        try:
            return datetime.datetime.strptime(day, f)
        except ValueError:
            continue
    return None

def _as_naive_now(now):
    """None -> bây giờ giờ VN · datetime -> bỏ tzinfo (quy ước _vn_now(): giờ-đồng-hồ VN) · date -> 00:00 ngày đó."""
    if isinstance(now, datetime.datetime):
        return now.replace(tzinfo=None)
    if isinstance(now, datetime.date):
        return datetime.datetime.combine(now, datetime.time.min)
    return _vn_now().replace(tzinfo=None)

def select_semester(semesters, now=None):
    """THUẦN — MỘT quy tắc chọn kỳ 'hiện tại' cho cả current_semester lẫn schedule.pick_semester, ĐÚNG như
    màn hình chính myFAP 2.0.5 (Mainpage, đọc từ bytecode: `res.find(inRange) || res.reduce(nearestStart)`):
      1) kỳ ĐẦU TIÊN theo thứ tự server trả có  startDate <= now <= endDate;
      2) không kỳ nào chứa `now` -> kỳ có startDate GẦN `now` nhất (|start − now|, CẢ HAI phía);
         hoà -> giữ kỳ đứng TRƯỚC trong danh sách (reduce chỉ thay khi gần hơn HẲN).
    So ở mức THỜI ĐIỂM như app (`new Date()` vs `new Date('…T00:00:00')`): endDate = 00:00 của ngày cuối
    ⇒ từ sau 00:00 NGÀY CUỐI kỳ đã KHÔNG còn 'trong kỳ' và rơi xuống bước 2 (thực tế ra kỳ kế tiếp —
    kỳ sau bắt đầu 2–3 ngày sau). Truyền `date` = mốc 00:00 của ngày đó.
    Bỏ qua mục không phải dict / thiếu semesterName / ngày lỗi (app sẽ kẹt ở mục NaN — ở đây bền hơn).
    Trả tên kỳ (đúng chính tả server), hoặc None nếu không kỳ nào dùng được -> caller tự fallback."""
    cur = _as_naive_now(now)
    rows = []
    for s in semesters or []:
        if isinstance(s, dict) and str(s.get("semesterName") or "").strip():
            rows.append((str(s.get("semesterName")), _sem_dt(s.get("startDate")), _sem_dt(s.get("endDate"))))
    for name, start, end in rows:
        if start and end and start <= cur <= end:
            return name
    best = None
    for name, start, _end in rows:
        if start is None:
            continue
        dist = abs((start - cur).total_seconds())
        if best is None or dist < best[0]:              # '<' HẲN: hoà giữ kỳ đứng trước (như app)
            best = (dist, name)
    return best[1] if best else None

def current_semester(token, campus, roll):
    """Trả tên học kỳ: env FAP_SEMESTER > tự dò qua GetSemester (select_semester) > đoán theo ngày (default_semester).
    HỢP ĐỒNG: LUÔN trả 1 chuỗi (không raise) — dashboard/bot_core/webui gộp nhiều mục, dựa vào điều này."""
    if os.environ.get("FAP_SEMESTER"):
        return os.environ["FAP_SEMESTER"]
    try:
        # checksum_login là override -> call() KHÔNG tự retry; call_login_retry lo phần thử ±1h (lệch giờ).
        out = call_login_retry("GetSemester", [("campusCode", campus), ("Authen", token)], roll, campus)
        # token hết hạn (kể cả thân kiểu v2) / checksum vẫn lỗi -> cảnh báo, đừng nuốt im
        if _err_code(out[1]) == "201" or is_session_expired(out[0], out[1]):
            print(f"⚠️ Không tự dò được học kỳ (GetSemester lỗi auth/checksum) — "
                  f"tạm dùng {default_semester()!r}. Đặt FAP_SEMESTER trong .env nếu sai.", file=sys.stderr)
            return default_semester()
        # parse AN TOÀN từng mục bên trong select_semester: 1 kỳ ngày lỗi KHÔNG làm hỏng cả việc dò (~28 kỳ).
        name = select_semester(as_list(out[1]))
        if name:
            return name
    except (Exception, SystemExit):     # SystemExit: call() v2 (thiếu khoá / token lệch phiên bản) — giữ hợp đồng
        pass                            # KHÔNG raise; lời gọi dữ liệu kế tiếp sẽ báo đúng lỗi đó cho người dùng
    return default_semester()
