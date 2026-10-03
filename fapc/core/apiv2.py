#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apiv2.py — API v2 của myFAP 2.0.5 (qua fap-proxy.fpt.edu.vn) — OPT-IN, THỬ NGHIỆM, CHƯA gọi thật lần nào.

Bật:  FAP_API_VERSION=v2  +  FAP_V2_KEY=<khoá ký lấy từ APK CỦA CHÍNH BẠN>   (xem docs/21-api-v2.md §5).
Mặc định v1 -> api.call() KHÔNG rẽ vào đây; hành vi v1 giữ NGUYÊN.

Cung cấp:
  normalize_version(raw)                -> THUẦN: ('v1'|'v2', hợp_lệ?)
  api_version()                         -> phiên bản đang cấu hình (giá trị lạ -> v1 + 1 cảnh báo song ngữ)
  v2_key()                              -> khoá ký FAP_V2_KEY; thiếu -> SystemExit song ngữ. KHÔNG BAO GIỜ in.
  checksum_v2(token, ts, key)           -> THUẦN: chữ ký header Checksum (phần trước dấu ':')
  build_headers_v2(token, campus, ts, key) -> THUẦN: header y như `_buildHeaders` của app
  v2_request(endpoint, params, roll, campus) -> THUẦN: (url v2, token) theo bảng ENDPOINTS
  session_version() / check_session_version(ver) -> token.json được đổi bằng API nào; lệch -> SystemExit
  call_v2(endpoint, params, roll, campus) -> GET qua proxy; CÙNG hợp đồng trả về với api.call()
  scrub(text)                           -> che khoá v2 (+ token) nếu lỡ lọt vào một chuỗi

Cơ chế — đọc từ bytecode myFAP 2.0.5 (versionCode 29) QUA công cụ có che dữ liệu, chưa gọi thử:
  _hmac256(msg)        = CryptoJS.HmacSHA256(msg, KHOÁ) -> Base64 -> replace(/=/g,'%3d') -> replace(/\\s/g,'+')
                         (KHOÁ là CHUỖI, CryptoJS coi chuỗi là byte UTF-8 -> KHÔNG hex-decode)
  _makeChecksum(ts, t) = _hmac256(t + 'MyFAP' + ts)   (t rỗng -> app thay bằng MỘT HẰNG nhúng khác — fap-cli
                         KHÔNG mang hằng đó nên KHÔNG BAO GIỜ gửi request v2 thiếu token)
  _buildHeaders(t, campus, extra) = {ClientCode:'MyFAP', CampusCode: campus||'', Authorization:'Bearer '+t
                         (bỏ khi t rỗng), Checksum: sig+':'+ts, Content-Type:'application/json'} + extra
  GET  = axios.get('https://fap-proxy.fpt.edu.vn/' + path, {headers, params, timeout: 15000})
  POST = axios.post(url, body||{}, {headers, params, timeout: 15000})  (chỉ dùng cho đăng nhập — auth.py)
  ts   = Math.floor(Date.now()/1000) — epoch GIÂY, KHÔNG theo giờ VN ⇒ không cần thử lại ±1h như v1.

⚠️ fap-cli CHỈ ĐỌC: endpoint GHI có trong sổ v2 của app nằm ở DENY và bị từ chối trước khi chạm mạng.
⚠️ Khoá v2 KHÔNG được nhúng/commit (khác tiền lệ SECRET của v1): người dùng tự trích từ APK của mình.
"""
import os, sys, json, time, hmac, hashlib, base64, urllib.parse
import requests
from . import paths
from . import api as _v1          # helper v1 dùng chung (cache, UA, nhận lỗi phiên); api.call() import ngược TRỄ
from .. import config

BASE_V2 = "https://fap-proxy.fpt.edu.vn/MyFAP"
TIMEOUT = 15                      # app: timeout 15000 ms cho mọi request v2
CLIENT_CODE = "MyFAP"
VERSIONS = ("v1", "v2")
TOKEN_JSON = paths.out("token.json")   # giống api.TOKEN_JSON (theo FAP_PROFILE); khai riêng để khỏi vòng import


# ---------- chọn phiên bản ----------
def normalize_version(raw):
    """THUẦN: giá trị thô FAP_API_VERSION -> (phiên bản, hợp lệ?). Rỗng/None -> ('v1', True).
    Bỏ khoảng trắng, không phân biệt hoa/thường ('V2' == 'v2'). Mọi thứ khác -> ('v1', False)."""
    s = str(raw if raw is not None else "").strip().lower()
    if not s:
        return "v1", True
    if s in VERSIONS:
        return s, True
    return "v1", False

_WARNED = {"bad_version": False}          # 1 lần / process (dict để test reset được)

def api_version():
    """Phiên bản API đang cấu hình ('v1' | 'v2'). Giá trị lạ -> 'v1' + ĐÚNG 1 cảnh báo song ngữ ra stderr.
    KHÔNG in lại giá trị đã gõ (lỡ dán nhầm khoá vào biến này thì cũng không lộ ra log)."""
    ver, ok = normalize_version(config.api_version_raw())
    if not ok and not _WARNED["bad_version"]:
        _WARNED["bad_version"] = True
        try:
            print("⚠️ FAP_API_VERSION không hợp lệ (chỉ nhận v1 | v2) — dùng v1.\n"
                  "⚠️ FAP_API_VERSION is invalid (only v1 | v2 are accepted) — using v1.", file=sys.stderr)
        except (OSError, ValueError):
            pass
    return ver


# ---------- khoá ký ----------
_MISSING_KEY_MSG = (
    "⚠️ FAP_API_VERSION=v2 nhưng chưa đặt FAP_V2_KEY (khoá ký của API v2 — fap-cli KHÔNG nhúng sẵn).\n"
    "   Trích từ CHÍNH bản APK myFAP chính thức của bạn (ghi thẳng vào .env, không in ra màn hình):\n"
    "     python analysis/apk_drift.py --write-v2-key <file.apk>\n"
    "   Hoặc bỏ FAP_API_VERSION (về v1). Xem docs/21-api-v2.md.\n"
    "⚠️ FAP_API_VERSION=v2 but FAP_V2_KEY is not set (the API v2 signing key — fap-cli does NOT ship it).\n"
    "   Extract it from YOUR OWN copy of the official myFAP APK (written straight to .env, never printed):\n"
    "     python analysis/apk_drift.py --write-v2-key <file.apk>\n"
    "   Or unset FAP_API_VERSION (back to v1). See docs/21-api-v2.md.")

def v2_key():
    """Khoá ký v2 từ FAP_V2_KEY (.env / biến môi trường). Thiếu -> SystemExit song ngữ (chỉ hướng dẫn, KHÔNG
    nhắc giá trị). Trả về để ký NGAY — đừng lưu vào biến module, đừng in, đừng nối vào thông báo lỗi."""
    k = str(config.v2_key_raw() or "").strip()
    if not k:
        raise SystemExit(_MISSING_KEY_MSG)
    return k

def scrub(text, *extra):
    """Che khoá v2 đang cấu hình (và các chuỗi bí mật truyền thêm, vd token) nếu lỡ lọt vào `text`.
    Lớp phòng thủ cuối: đường v2 vốn KHÔNG nội suy khoá/str(exception) vào thông báo nào."""
    s = str(text)
    for secret in (str(config.v2_key_raw() or "").strip(),) + tuple(str(x or "") for x in extra):
        if len(secret) >= 4:                         # bỏ qua chuỗi quá ngắn (che nhầm cả câu)
            s = s.replace(secret, "***")
    return s


# ---------- chữ ký + header (THUẦN) ----------
def checksum_v2(token, ts, key):
    """THUẦN: base64(HMAC_SHA256(key_utf8, token + 'MyFAP' + str(ts))), '=' -> '%3d', ' ' -> '+'.
    `key` dùng NGUYÊN chuỗi làm byte UTF-8 (KHÔNG hex-decode) — đúng CryptoJS.HmacSHA256(msg, '<chuỗi>').
    App thay mọi khoảng trắng (/\\s/g) bằng '+'; Base64 không có khoảng trắng nên tương đương."""
    msg = "{}{}{}".format(token if token is not None else "", CLIENT_CODE, int(ts))
    sig = base64.b64encode(hmac.new(str(key).encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest())
    return sig.decode("ascii").replace("=", "%3d").replace(" ", "+")

def build_headers_v2(token, campus, ts, key):
    """THUẦN: header của MỘT request v2, đúng `_buildHeaders` của app (thứ tự khoá giữ như app).
    token rỗng -> KHÔNG có Authorization (như app). NHƯNG khi đó app ký bằng một hằng nhúng mà fap-cli không
    mang ⇒ chữ ký ở đây sẽ SAI — tầng gọi (call_v2/auth) luôn đòi token khác rỗng, không bao giờ gửi ca này."""
    ts = int(ts)
    h = {"ClientCode": CLIENT_CODE, "CampusCode": str(campus or "")}
    if token:
        h["Authorization"] = "Bearer " + str(token)
    h["Checksum"] = "{}:{}".format(checksum_v2(token or "", ts, key), ts)
    h["Content-Type"] = "application/json"
    return h


# ---------- bảng endpoint v2 ----------
# Khoá = tên v1 ĐÚNG như call site truyền vào api.call() (tra KHÔNG phân biệt hoa/thường).
# Giá trị = (đường dẫn v2, method, tham số query theo ĐÚNG thứ tự object của app).
# Đọc từ adapter v2 của myFAP 2.0.5 (bytecode, hàm #7085–#7213; helper GET = env slot 21, POST = slot 22):
# MỌI endpoint dưới đây đi helper GET. Giá trị tham số lấy từ params v1 (tra không phân biệt hoa/thường:
# 'campusCode' -> 'CampusCode', 'Semester'/'semester'…); thiếu CampusCode/rollNumber thì lấy campus/roll
# của call(). Tham số v1 KHÔNG có trong bảng thì KHÔNG gửi (vd SubjectCode của GetMarkByCourse — app v2 không gửi).
# 'Authen' trên query: CHỈ những endpoint app vẫn gửi (CheckUpdateProfile, GetSemesterMark, GetApplication,
# CheckOpenFeedBack, GetNotificationByRoll; GetNotificationByDonor/AddRate fap-cli không gọi).
ENDPOINTS = {
    "GetStudentById":           ("GetStudentById",           "GET", ("rollNumber", "CampusCode")),
    "CheckUpdateProfile":       ("CheckUpdateProfile",       "GET", ("CampusCode", "rollNumber", "Authen")),
    "GetSemester":              ("GetSemester",              "GET", ()),
    "GetSubjets":               ("GetSubjets",               "GET", ("CampusCode",)),
    "GetSubjectBySemester":     ("GetSubjectBySemester",     "GET", ("CampusCode", "Semester")),
    "GetCourseOfSemester":      ("GetCourseOfSemester",      "GET", ("CampusCode", "semester", "rollNumber")),
    "GetStudentMark":           ("GetStudentMark",           "GET", ("CampusCode", "rollNumber", "Semester")),
    "GetSemesterMark":          ("GetSemesterMark",          "GET", ("CampusCode", "rollNumber", "Authen")),
    "GetMarkByCourse":          ("GetMarkByCourse",          "GET", ("CampusCode", "CourseId", "rollNumber")),
    "AcademicTranscript":       ("AcademicTranscript",       "GET", ("CampusCode", "rollNumber")),
    "GetDiemphongtrao":         ("GetDiemphongtrao",         "GET", ("CampusCode", "rollNumber", "semester")),
    "GetActivityStudent":       ("GetActivityStudent",       "GET", ("CampusCode", "rollNumber", "Semester")),
    "GetActivityStudentByWeek": ("GetActivityStudentByWeek", "GET", ("CampusCode", "week", "rollNumber", "Semester", "year")),
    "GetScheduleExam":          ("GetScheduleExam",          "GET", ("CampusCode", "rollNumber", "Semester")),
    "GetWeekByDate":            ("GetWeekByDate",            "GET", ("date",)),
    "GetStudentAttendances":    ("GetStudentAttendances",    "GET", ("CampusCode", "Semester", "rollNumber")),
    # v1 viết thường 'getCourseAttendance' (call site giữ nguyên) -> v2 viết HOA chữ đầu.
    "getCourseAttendance":      ("GetCourseAttendance",      "GET", ("CampusCode", "rollNumber", "Semester", "SubjectCode", "ClassName")),
    "GeFeeByRoll":              ("GeFeeByRoll",              "GET", ("CampusCode", "rollNumber")),
    "GetBalance":               ("GetBalance",               "GET", ("CampusCode", "rollNumber")),
    "GetTop10News":             ("GetTop10News",             "GET", ("CampusCode", "type")),
    "SearchNews":               ("SearchNews",               "GET", ("CampusCode", "type", "keysearch")),
    "GetApplication":           ("GetApplication",           "GET", ("CampusCode", "rollNumber", "Authen")),
    "CheckOpenFeedBack":        ("CheckOpenFeedBack",        "GET", ("CampusCode", "rollNumber", "Authen")),
    "GetNotificationByRoll":    ("GetNotificationByRoll",    "GET", ("CampusCode", "rollNumber", "Authen")),
    "GetCampusInfo":            ("GetCampusInfo",            "GET", ("CampusCode", "rollNumber")),
}
# fap-cli ký MỌI request v2 bằng Bearer + Checksum của CHÍNH token bạn (không mang hằng nào của app).
# Luôn đi v1, không cần token: app gọi bản v2 bằng BEARER TĨNH nhúng trong app (danh tính của app, không phải
# của bạn) — fap-cli không mượn. `fap campuses` vì vậy vẫn chạy trước khi đăng nhập.
V1_ONLY = frozenset({"GetAllActiveCampus"})
# Có trong v1 nhưng v2 KHÔNG có request thật: adapter v2 của app trả [] cố định (#7179/#7181).
V2_UNAVAILABLE = frozenset({"GetStudentRate"})
# DENY: endpoint GHI (fap-cli chỉ ĐỌC) + GetApiActive (cần bearer tĩnh của app). Không bao giờ gửi.
DENY = frozenset({"AddRate", "SubmitStudentFeedback", "UpdateTokedevices", "UpdateTokenDonor", "GetApiActive"})

_BY_LOWER = {k.lower(): v for k, v in ENDPOINTS.items()}
_DENY_LOWER = frozenset(x.lower() for x in DENY)
_UNAVAILABLE_LOWER = frozenset(x.lower() for x in V2_UNAVAILABLE)

def is_unavailable(endpoint):
    """THUẦN: endpoint v1 này KHÔNG có trên v2 (adapter app trả [] cố định) -> caller nên bỏ qua."""
    return str(endpoint or "").lower() in _UNAVAILABLE_LOWER

def v2_request(endpoint, params, roll="", campus=""):
    """THUẦN (không mạng, không đọc khoá): (endpoint v1, params v1) -> (url v2 đầy đủ, token).
    SystemExit song ngữ nếu endpoint bị cấm / không có trên v2 / chưa có ánh xạ / thiếu token (Authen)."""
    name = str(endpoint or "")
    low = name.lower()
    if low in _DENY_LOWER:
        raise SystemExit(f"⛔ {name}: endpoint GHI/cấm — fap-cli chỉ ĐỌC, không gửi qua API v2.\n"
                         f"⛔ {name}: write/forbidden endpoint — fap-cli is read-only; never sent over API v2.")
    if low in _UNAVAILABLE_LOWER:
        raise SystemExit(f"ℹ️ {name}: không có trên API v2 (app chính thức trả rỗng cố định).\n"
                         f"ℹ️ {name}: not available on API v2 (the official app returns a fixed empty list).")
    spec = _BY_LOWER.get(low)
    if spec is None:
        raise SystemExit(f"⚠️ {name}: chưa có ánh xạ API v2 trong fap-cli (fapc/core/apiv2.py). Bỏ FAP_API_VERSION để về v1.\n"
                         f"⚠️ {name}: no API v2 mapping in fap-cli yet (fapc/core/apiv2.py). Unset FAP_API_VERSION to use v1.")
    path, _method, keys = spec
    vals = {}
    for k, v in params or []:
        vals.setdefault(str(k).lower(), v)                  # params v1 có thể lặp khoá: giữ giá trị ĐẦU như query v1
    token = str(vals.get("authen") or "")
    if not token:
        raise SystemExit("⚠️ API v2 cần token đăng nhập — chạy:  fap login  (hoặc /login trong chat bot).\n"
                         "⚠️ API v2 needs a sign-in token — run:  fap login  (or send /login to the bot).")
    fallback = {"campuscode": campus, "rollnumber": roll}
    q = []
    for k in keys:
        v = vals.get(k.lower())
        if v is None:
            v = fallback.get(k.lower())
        if v is None:                                     # axios bỏ tham số null/undefined; '' vẫn gửi
            continue
        q.append((k, v))
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in q)
    return f"{BASE_V2}/{path}" + (f"?{qs}" if qs else ""), token


# ---------- phiên gắn phiên bản (token.json) ----------
_SESSION_CACHE = {}

def session_version(path=None):
    """Phiên bản API đã dùng để đổi token trong token.json: 'v1' | 'v2'. Token cũ (trước tính năng này) không
    có khoá `api_version` -> 'v1'. KHÔNG có file -> None (chưa đăng nhập: để creds() báo lỗi đúng của nó).
    Cache theo (mtime, size) để call() khỏi đọc lại JSON mỗi lần."""
    p = path or TOKEN_JSON
    try:
        st = os.stat(p)
    except OSError:
        return None
    sig = (st.st_mtime_ns, st.st_size)
    hit = _SESSION_CACHE.get(p)
    if hit and hit[0] == sig:
        return hit[1]
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f).get("api_version")
    except OSError:
        return None                                       # lỗi đọc TẠM THỜI (khoá file/AV…): KHÔNG cache, lần sau đọc lại
    except (ValueError, AttributeError):
        raw = None                                        # nội dung hỏng: cố định theo chữ ký file -> cache được
    ver = normalize_version(raw)[0]                       # thiếu/lạ -> v1 (mọi token cũ đều là v1)
    _SESSION_CACHE[p] = (sig, ver)
    return ver

def check_session_version(configured, path=None):
    """Token.json được đổi bằng phiên bản KHÁC FAP_API_VERSION hiện tại -> SystemExit song ngữ bảo `fap refresh`
    (refresh đổi lại token theo phiên bản đang cấu hình). Giống app 2.0.5: lệch `sessionApiVersion` -> đăng xuất."""
    have = session_version(path)
    if have is None or have == configured:
        return
    raise SystemExit(
        f"⚠️ Token hiện tại được cấp qua API {have} nhưng FAP_API_VERSION={configured} — bạn vừa đổi phiên bản API.\n"
        f"   Chạy:  fap refresh  (hoặc /login trong chat bot) để đổi token theo {configured}, rồi thử lại.\n"
        f"⚠️ The current token was issued via API {have} but FAP_API_VERSION={configured} — you switched API versions.\n"
        f"   Run:  fap refresh  (or send /login to the bot) to re-exchange the token for {configured}, then retry.")


# ---------- transport v2 ----------
def call_v2(endpoint, params, roll, campus, timeout=TIMEOUT):
    """GET https://fap-proxy.fpt.edu.vn/MyFAP/<Name>?<params> với header ký v2. CÙNG hợp đồng với api.call():
    trả (http_status|None, json|text|thông-báo-lỗi). Không thử lại ±1h (chữ ký theo epoch giây).
    allow_redirects=False: 7 endpoint vẫn có Authen=<token> trên query -> không theo 30x sang host khác.
    Cache trong-bộ-nhớ dùng CHUNG với v1 (FAP_CACHE_MIN) nhưng tách khoá 'v2|…' để không trộn phản hồi."""
    url, token = v2_request(endpoint, params, roll, campus)   # cấm/thiếu ánh xạ/thiếu token -> SystemExit, 0 request
    key = v2_key()                                             # thiếu khoá -> SystemExit, 0 request
    ttl = _v1._cache_ttl()
    ck = ("v2|" + url[len(BASE_V2):]) if ttl > 0 else None
    if ck is not None:
        hit = _v1._CACHE.get(ck)
        if hit and hit[0] > time.time():
            return hit[1]
    headers = dict(_v1.UA)
    headers.update(build_headers_v2(token, campus, int(time.time()), key))
    try:
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=False)
    except requests.RequestException as e:
        # KHÔNG nội suy str(e): chuỗi requests nhúng url (Authen=<token> ở 7 endpoint). Khoá không bao giờ ở đây.
        return None, f"Lỗi mạng ({type(e).__name__}) khi gọi {endpoint}"
    try:
        out = (r.status_code, r.json())
    except ValueError:
        out = (r.status_code, r.text)
    if ck is not None and out[0] == 200 and _v1._err_code(out[1]) != "201" \
            and not _v1.is_session_expired(out[0], out[1]):
        _v1._CACHE[ck] = (time.time() + ttl, out)
    return out
