#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apk_drift.py — KIỂM "TRÔI" (drift) của bản build myFAP so với hằng số fap-cli — OFFLINE, thư viện chuẩn.

So một bản build (APK hoặc raw Hermes bundle) với những gì fap-cli ĐANG dựa vào, hoặc diff hai bản,
để biết NGAY khi FPT cập nhật app có đụng tới endpoint / host / khoá ký mà fap-cli cần hay không.

    python analysis/apk_drift.py <apk|bundle>                      # kiểm 1 build vs hằng số/endpoint fap-cli
    python analysis/apk_drift.py <old.apk|bundle> <new.apk|bundle> # diff 2 build (case-SENSITIVE)
    python analysis/apk_drift.py --write-v2-key <apk|bundle> [--env-file PATH]

Nhận APK base (zip chứa assets/index.android.bundle) HOẶC raw Hermes bundle. Chỉ ĐỌC, không gọi mạng.
Phân tích bytecode cần hermes-dec hoặc hbc-disassembler (chỉ cho --write-v2-key); phần báo cáo drift dùng
bộ đọc bảng-chuỗi HBC thuần thư viện chuẩn (bytecode version 96).

QUYỀN RIÊNG TƯ: bundle app có khoá nhúng + DỮ LIỆU CÁ NHÂN của người khác. Mọi chuỗi IN RA đều qua safe()
(che credential, hex≥12 có chữ số, email, mã SV, JWT, dãy số dài, token dài, tên riêng VN) — chỉ in chuỗi
dạng ĐỊNH DANH. Giá trị khoá/secret KHÔNG BAO GIỜ in ra, kể cả --write-v2-key (chỉ in độ dài + sha256[:8]).

EN — Offline drift check of a myFAP build against the constants/endpoints fap-cli relies on (or a diff of
two builds). Accepts a base APK (zip with assets/index.android.bundle) or a raw Hermes bundle; stdlib only
for the report (a small HBC string-table reader for bytecode v96). Every printed string is masked; secret
values are never printed. Exit 1 when something fap-cli depends on changed; 2 on corrupt/unsupported input
or a --write-v2-key refusal; 0 otherwise (cron/CI friendly).
"""
import argparse
import ast
import errno
import hashlib
import os
import re
import struct
import sys
import zipfile
import zlib
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# safe() — PORT NGUYÊN RULE từ analysis/safe_hasm.py: chỉ in chuỗi an toàn (định danh/nhãn).
# Giữ y hệt để báo cáo không bao giờ rò khoá/PII. KHÔNG nới lỏng mà không soát lại.
# ---------------------------------------------------------------------------
_ROLL = re.compile(r"[A-Za-z]{2,}\d{5,7}")        # KHÔNG word-boundary: bắt cả fe_xx1234567
_SURNAMES = ("nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ", "đặng", "bùi", "đỗ", "hồ",
             "ngô", "dương", "lý", "đinh", "trương", "mai", "đoàn", "lâm", "tô", "cao", "hà", "lưu", "tạ", "châu")


def safe(s):
    """Trả s nếu an toàn để hiện, nếu không trả '<masked:KIND>'. (giống safe_hasm.safe)"""
    t = str(s).strip()
    low = t.lower()
    if re.search(r"(?i)\b(bearer|basic|token|apikey|api_key|secret)\s*[:=]?\s+\S{8,}", t):
        return "<masked:credential>"
    if re.search(r"[A-Fa-f0-9]{12,}", t) and re.search(r"\d", t):
        return "<masked:hex>"                      # khoá/id, kể cả hex hằng ngắn (12+)
    if "@" in t:                                   return "<masked:email>"
    if _ROLL.search(t):                            return "<masked:roll>"
    if t.startswith("eyJ"):                        return "<masked:jwt>"
    if re.search(r"\d{9,}", t):                    return "<masked:number>"
    if re.fullmatch(r"[A-Fa-f0-9]{24,}", t):       return "<masked:hex>"
    if " " not in t and len(t) >= 32 and re.search(r"\d", t) and re.search(r"[A-Za-z]", t) and not t.startswith(("http", "/")):
        return "<masked:token>"
    if re.fullmatch(r"[A-Za-z0-9+/=_-]{40,}", t):  return "<masked:token>"
    words = t.split()
    if 2 <= len(words) <= 5 and all(w[:1].isupper() and w.isalpha() for w in words):
        if words[0].lower() in _SURNAMES or any(ord(c) > 127 for c in t):
            return "<masked:name?>"
    if low.startswith(("http://", "https://")):
        return re.sub(r"([?&][^=&]+=)[^&]*", r"\1<v>", t)    # giữ scheme/host/path, giấu giá trị query
    return t


def _looks_secret(s):
    """Chuỗi 'dạng khoá' (hex≥12 có chữ số) — để đếm/so, KHÔNG in giá trị."""
    return bool(re.search(r"[A-Fa-f0-9]{12,}", s) and re.search(r"\d", s))


# ---------------------------------------------------------------------------
# Bộ đọc bảng chuỗi Hermes HBC (chỉ thư viện chuẩn) — đủ cho báo cáo drift.
# Bố cục header/bảng chuỗi tham chiếu facebook/hermes BytecodeFileFormat.h và hermes-dec.
# Chỉ hỗ trợ dải version 84..96 (bố cục header + small function header 16 byte giống v96).
# ---------------------------------------------------------------------------
HBC_MAGIC = 0x1F1903C103BC1FC6
SHA1_LEN = 20
SUPPORTED = range(84, 97)          # 84..96 — bản 2.0.4/2.0.5 là 96; fail rõ ngoài dải này


class HBCError(ValueError):
    pass


class HBC:
    """Đọc version + toàn bộ string literal của một bundle Hermes. KHÔNG decode bytecode."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.version = 0
        self.strings = []
        self._parse()

    # --- tiện ích đọc ---
    def _need(self, end, what):
        """Vùng [.., end) phải nằm TRONG file — input cắt cụt / số đếm rác -> HBCError (exit 2), không struct.error."""
        if end > len(self.data):
            raise HBCError("%s vượt quá cuối file (bị cắt cụt?) · %s past end of file (truncated?)" % (what, what))

    def _u32(self):
        self._need(self.pos + 4, "header")
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def _align(self, n):
        rem = self.pos % n
        if rem:
            self.pos += n - rem

    def _parse(self):
        d = self.data
        if len(d) < 32:
            raise HBCError("file quá nhỏ, không phải Hermes bundle · file too small")
        magic = struct.unpack_from("<Q", d, 0)[0]
        if magic != HBC_MAGIC:
            raise HBCError("không có magic Hermes · not a Hermes bytecode file")
        self.version = struct.unpack_from("<I", d, 8)[0]
        if self.version not in SUPPORTED:
            raise HBCError("bytecode version %d chưa hỗ trợ (chỉ %d..%d) · unsupported version"
                           % (self.version, SUPPORTED.start, SUPPORTED.stop - 1))
        v = self.version
        # Header: magic(8) + version(4) + sourceHash(20) = 32, rồi các u32:
        self.pos = 32
        self._u32()   # fileLength
        self._u32()   # globalCodeIndex
        function_count = self._u32()
        string_kind_count = self._u32()
        identifier_count = self._u32()
        string_count = self._u32()
        overflow_string_count = self._u32()
        string_storage_size = self._u32()
        if v >= 87:
            self._u32(); self._u32()          # bigIntCount, bigIntStorageSize
        self._u32(); self._u32()              # regExpCount, regExpStorageSize
        self._u32(); self._u32(); self._u32() # arrayBufferSize, objKeyBufferSize, objValueBufferSize (v<97)
        self._u32(); self._u32()              # segmentID, cjsModuleCount
        if v >= 84:
            self._u32()                       # functionSourceCount
        self._u32()                           # debugInfoOffset
        self.pos += 1                         # 3 bit cờ (staticBuiltins/cjsResolved/hasAsync) gói trong 1 byte
        self._need(self.pos, "header")
        # Padding căn 32 trước bảng function headers. MỖI bảng phải nằm trọn trong file (_need) — số đếm
        # rác/cắt cụt báo HBCError NGAY, không nhảy pos ra ngoài rồi vỡ struct.error ở chỗ khác.
        self._align(32)
        # Small function headers: v<98 = 16 byte/function; chỉ cần NHẢY QUA (không parse phần phụ).
        self.pos += function_count * 16
        self._need(self.pos, "function headers")
        # String kinds (RLE), 4 byte/entry
        self._align(4)
        self.pos += string_kind_count * 4
        self._need(self.pos, "string kinds")
        # Identifier hashes, 4 byte/entry
        self._align(4)
        self.pos += identifier_count * 4
        self._need(self.pos, "identifier hashes")
        # Small string table, 4 byte/entry
        self._align(4)
        small_off = self.pos
        self.pos += string_count * 4
        self._need(self.pos, "small string table")
        # Overflow string table, 8 byte/entry (offset u32 + length u32)
        self._align(4)
        overflow_off = self.pos
        self.pos += overflow_string_count * 8
        self._need(self.pos, "overflow string table")
        # String storage
        self._align(4)
        storage_off = self.pos
        storage = d[storage_off:storage_off + string_storage_size]
        if len(storage) < string_storage_size:
            raise HBCError("string storage bị cắt cụt · truncated string storage")
        self.strings = self._decode_strings(
            d, small_off, string_count, overflow_off, overflow_string_count, storage)

    @staticmethod
    def _decode_strings(d, small_off, string_count, overflow_off, overflow_count, storage):
        out = []
        for i in range(string_count):
            entry = struct.unpack_from("<I", d, small_off + i * 4)[0]
            is_utf16 = entry & 0x1
            offset = (entry >> 1) & 0x7FFFFF
            length = (entry >> 24) & 0xFF
            if length == 0xFF:                      # escape -> tra bảng overflow
                if offset >= overflow_count:
                    raise HBCError("chuỗi #%d trỏ ngoài bảng overflow · string #%d points past the overflow table"
                                   % (i, i))
                ov = overflow_off + offset * 8
                offset, length = struct.unpack_from("<II", d, ov)
            nbytes = length * 2 if is_utf16 else length
            if offset + nbytes > len(storage):
                raise HBCError("chuỗi #%d nằm ngoài string storage · string #%d lies outside string storage"
                               % (i, i))
            if is_utf16:
                raw = storage[offset:offset + nbytes]
                out.append(raw.decode("utf-16-le", errors="surrogatepass"))
            else:
                raw = storage[offset:offset + nbytes]
                out.append("".join(chr(b) for b in raw))   # 1 byte = 1 codepoint (giống hermes-dec)
        return out


# ---------------------------------------------------------------------------
# Nạp byte bundle từ APK (zip) hoặc file raw.
# ---------------------------------------------------------------------------
BUNDLE_ENTRY = "assets/index.android.bundle"


def load_bundle(path):
    """Trả (bytes, nguồn). APK -> rút assets/index.android.bundle; nếu không -> đọc raw."""
    if not os.path.isfile(path):
        raise HBCError("không thấy file · no such file: %s" % safe(path))
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:2] == b"PK":                           # zip/APK
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if BUNDLE_ENTRY not in names:
                cand = [n for n in names if n.endswith("index.android.bundle")]
                if not cand:
                    raise HBCError("APK không có %s · no RN bundle in APK" % BUNDLE_ENTRY)
                entry = cand[0]
            else:
                entry = BUNDLE_ENTRY
            return z.read(entry), "APK:%s" % entry
    with open(path, "rb") as f:
        return f.read(), "bundle"


# ---------------------------------------------------------------------------
# Rút endpoint / host / marker từ danh sách chuỗi.
# ---------------------------------------------------------------------------
V1_PREFIX = "https://api.fpt.edu.vn/fap/api/MyFAP/"
SURVEY_HOST = "https://survey.fpt.edu.vn"
PROXY_BASE = "https://fap-proxy.fpt.edu.vn"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def _endpoint_name(after):
    """Lấy tên endpoint ở đầu `after` (tới dấu ? hoặc hết)."""
    seg = after.split("?", 1)[0].split("/", 1)[0]
    m = _NAME.match(seg)
    return m.group(0) if m and m.group(0) == seg else None


def _host_of(s):
    """CHỈ 'scheme://hostname[:port]' của một literal URL http(s), hoặc None.

    Bỏ path, ;params, ?query, #fragment, user:pass@ — các phần đó có thể mang token/PII và trước đây lọt
    nguyên vào danh sách Host (regex cũ chỉ dừng ở / ? khoảng trắng). Kết quả VẪN qua safe() khi in."""
    if not s.startswith(("http://", "https://")):
        return None
    tok = s.split(None, 1)[0]                       # literal kiểu 'https://x.y nội dung…' -> chỉ token đầu
    try:
        u = urlsplit(tok)
        host = u.hostname
        port = u.port                               # cổng rác ('x.y:abc', >65535) -> ValueError
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not host:
        return None
    if ":" in host:                                 # IPv6 (chỉ có khi trong [..]) -> hex/:/. , giữ ngoặc vuông
        if not re.fullmatch(r"[0-9a-f:.]+", host):
            return None
        host = "[%s]" % host
    else:
        # urlsplit KHÔNG coi ';' là hết netloc: 'https://h;jsessionid=…' cho hostname 'h;jsessionid=…'
        # -> cắt ở ký tự đầu tiên không thuộc tên host.
        m = re.match(r"[\w.*-]+", host)
        if not m:
            return None
        host = m.group(0)
    return "%s://%s%s" % (u.scheme, host, ":%d" % port if port is not None else "")


def extract(strings):
    """Trả dict các tập đã rút (toàn chuỗi dạng định danh — an toàn in)."""
    v1 = set()
    survey = set()
    v2 = set()
    hosts = set()
    for s in strings:
        if s.startswith(V1_PREFIX):
            n = _endpoint_name(s[len(V1_PREFIX):])
            if n:
                v1.add(n)
        if s.startswith(SURVEY_HOST):
            m = re.search(r"/(?:API|api)/myFAP/([A-Za-z][A-Za-z0-9]*)", s)
            if m:
                survey.add(m.group(1))
        m2 = re.fullmatch(r"MyFAP/([A-Za-z][A-Za-z0-9]*)", s)
        if m2:
            v2.add(m2.group(1))
        h = _host_of(s)
        if h:
            hosts.add(h)
    markers = {
        "GetApiActive": "GetApiActive" in v2 or any(s == "MyFAP/GetApiActive" for s in strings),
        "sessionApiVersion": "sessionApiVersion" in strings,
        "OTA": any(("[OTA]" in s) or ("useOtaUpdate" in s) or s.startswith("OTA ") or s.startswith("OTA:") for s in strings),
        "v1_literal": "v1" in strings,
        "v2_literal": "v2" in strings,
        "fap_proxy": any(s.startswith(PROXY_BASE) for s in strings),
    }
    return {"v1": v1, "survey": survey, "v2": v2, "hosts": hosts, "markers": markers}


# ---------------------------------------------------------------------------
# Hằng số + endpoint fap-cli TỰ KHAI (đọc từ mã nguồn repo, qua ast — KHÔNG import, KHÔNG chạy).
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LEGACY_AST = sys.version_info < (3, 8)     # 3.7: literal chuỗi là ast.Str (.s), chưa phải ast.Constant


def _str_lit(node):
    """Giá trị literal chuỗi của 1 node ast, hoặc None. 3.8+: ast.Constant; 3.7: ast.Str (.s).

    Chỉ ĐỌC tên lớp 'Str' trên 3.7 — KHÔNG chạm ast.Str ở 3.8+ (deprecated, bị gỡ ở 3.14). Thiếu nhánh
    3.7 thì mọi lần chạy báo SECRET/BASE 'thiếu' (đọc không ra hằng nào)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if _LEGACY_AST and type(node).__name__ == "Str":
        s = getattr(node, "s", None)
        return s if isinstance(s, str) else None
    return None


def _read_source(py_path):
    """Mã nguồn 1 file repo, hoặc None nếu không đọc được (thiếu file, không phải UTF-8)."""
    try:
        with open(py_path, encoding="utf-8") as f:
            return f.read()
    except (OSError, ValueError):
        return None


def _parse_source(py_path):
    src = _read_source(py_path)
    if src is None:
        return None
    try:
        return ast.parse(src)
    except (SyntaxError, ValueError):
        return None


def _const_strings(py_path, names):
    """Trả {name: value} cho các gán hằng chuỗi cấp module (ast, không thực thi)."""
    out = {}
    tree = _parse_source(py_path)
    if tree is None:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nm = node.targets[0].id
            val = _str_lit(node.value)
            if nm in names and val is not None:
                out[nm] = val
    return out


def fapcli_constants(root=REPO_ROOT):
    """Giá trị hằng fap-cli cần (KHÔNG in ra). Trả {} nếu chạy ngoài repo."""
    api_py = os.path.join(root, "fapc", "core", "api.py")
    auth_py = os.path.join(root, "fapc", "core", "auth.py")
    c = {}
    c.update(_const_strings(api_py, {"SECRET", "LOGIN_PREFIX", "BASE"}))
    c.update(_const_strings(auth_py, {"CLIENT_ID", "ISSUER", "REDIRECT_URI"}))
    return c


_CALL = re.compile(r"""call(?:_login_retry)?\(\s*["']([A-Za-z][A-Za-z0-9]*)["']""")
# Endpoint dựng URL TRỰC TIẾP (không qua call("…")) — vd fapc/core/auth.py:
#   f"{FAP_BASE}/AuthenticationByFeId?campusCode=…"   (v1)   ·   f"{apiv2.BASE_V2}/AuthenticationByFeId"   (v2)
# Thiếu regex này thì build BỎ AuthenticationByFeId (đăng nhập!) vẫn ra ✅ + exit 0. Bắt cả dạng nối chuỗi
# BASE + "/Name". KHÔNG bắt f"{BASE_V2}/{path}" (tên động) hay f"{base}/{endpoint}" (biến thường).
_URL_EP = re.compile(r"""(?:\{(?:[A-Za-z_][A-Za-z0-9_]*\.)?(?:FAP_BASE|BASE|BASE_V2|V2_BASE)\}/"""
                     r"""|\b(?:FAP_BASE|BASE|BASE_V2|V2_BASE)\s*\+\s*["']/)([A-Za-z][A-Za-z0-9]*)""")


def fapcli_endpoints(root=REPO_ROOT):
    """Tên endpoint fap-cli THỰC SỰ gọi: mọi call("Name" + URL dựng từ BASE ("{BASE}/Name") + khoá dict
    SIMPLE trong extract.py."""
    eps = set()
    fapc_dir = os.path.join(root, "fapc")
    for dirpath, _dirs, files in os.walk(fapc_dir):
        for fn in files:
            if fn.endswith(".py"):
                txt = _read_source(os.path.join(dirpath, fn))
                if txt is None:
                    continue
                eps.update(_CALL.findall(txt))
                eps.update(_URL_EP.findall(txt))
    # Khoá dict SIMPLE trong extract.py (endpoint 'fap extract' quét) — đọc qua ast.
    eps.update(_simple_keys(os.path.join(fapc_dir, "core", "extract.py")))
    return eps


def _simple_keys(extract_py):
    tree = _parse_source(extract_py)
    if tree is None:
        return set()
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SIMPLE" and \
                isinstance(node.value, ast.Dict):
            for k in node.value.keys:
                val = _str_lit(k) if k is not None else None     # k None = '**other' trong dict
                if val is not None:
                    keys.add(val)
    return keys


def _present(value, strings_set, strings):
    """Hằng có trong bundle không (bool). Thử khớp đúng rồi tới chứa-trong (prefix URL/substring)."""
    if value in strings_set:
        return True
    return any(value in s for s in strings)


# ---------------------------------------------------------------------------
# Báo cáo.
# ---------------------------------------------------------------------------
def _t(vi, en):
    return en if str(os.environ.get("FAP_LANG", "vi")).lower().startswith("en") else vi


def _sorted(names):
    return sorted(safe(n) for n in names)


# Hằng fap-cli kiểm trong build — thứ tự in. Hằng nào ĐỌC ĐƯỢC từ repo mà THIẾU trong build => exit 1.
CONST_NAMES = ("SECRET", "LOGIN_PREFIX", "BASE", "CLIENT_ID", "ISSUER", "REDIRECT_URI")
# Hằng BẮT BUỘC đọc được từ repo: không đọc ra (đổi tên/di chuyển trong api.py) = tool mất khả năng kiểm
# đúng thứ quan trọng nhất -> vẫn exit 1 (như trước), nhưng báo ĐÚNG lý do thay vì "không thấy trong build".
REQUIRED_CONSTS = ("SECRET", "BASE")


def const_check(consts, strings_set, strings):
    """THUẦN: (missing, unreadable) — chỉ TÊN hằng, không bao giờ giá trị.
    missing = đọc được từ repo nhưng THIẾU trong build; unreadable = hằng bắt buộc không đọc được từ repo."""
    missing = [n for n in CONST_NAMES if n in consts and not _present(consts[n], strings_set, strings)]
    unreadable = [n for n in REQUIRED_CONSTS if n not in consts]
    return missing, unreadable


def analyze(data, root=REPO_ROOT):
    """Trả (info, consts, eps, missing_eps, const_missing, const_unreadable) cho 1 build (chỉ TÊN, không giá trị)."""
    hbc = HBC(data)
    info = extract(hbc.strings)
    info["version"] = hbc.version
    info["string_count"] = len(hbc.strings)
    consts = fapcli_constants(root)
    eps = fapcli_endpoints(root)
    ss = set(hbc.strings)
    # endpoint fap-cli gọi NHƯNG bundle không có (so không phân biệt hoa/thường? KHÔNG — v1 giữ nguyên,
    # getCourseAttendance viết thường ở v1). So case-SENSITIVE với tập v1 ∪ survey của bundle.
    bundle_eps = set(info["v1"]) | set(info["survey"])
    missing = sorted(e for e in eps if e not in bundle_eps)
    const_missing, const_unreadable = const_check(consts, ss, hbc.strings)
    info["_hbc"] = hbc
    return info, consts, eps, missing, const_missing, const_unreadable


def _const_label(name):
    return {"SECRET": _t("secret HMAC v1", "v1 HMAC secret"),
            "LOGIN_PREFIX": _t("tiền tố login", "login prefix")}.get(name, name)


def _print_const_presence(consts, ss, strings):
    for name in CONST_NAMES:
        lbl = _const_label(name)
        if name in consts:
            ok = _present(consts[name], ss, strings)
            print("    %-14s %s" % (lbl, _t("CÓ", "present") if ok else _t("THIẾU", "MISSING")))
        else:
            print("    %-14s %s" % (lbl, _t("(không đọc được từ repo)", "(not readable from repo)")))


def _warn_consts(const_missing, const_unreadable, where):
    """In 1 dòng ⚠️ cho MỖI hằng thiếu / không đọc được — CHỈ TÊN hằng, không bao giờ giá trị."""
    for n in const_missing:
        print(_t("  ⚠️ hằng fap-cli %s KHÔNG thấy trong %s", "  ⚠️ fap-cli constant %s not found in %s")
              % (n, where))
    for n in const_unreadable:
        print(_t("  ⚠️ hằng fap-cli %s không đọc được từ repo — không kiểm được",
                 "  ⚠️ fap-cli constant %s not readable from the repo — cannot check") % n)


def report_one(path, root=REPO_ROOT):
    data, src = load_bundle(path)
    info, consts, eps, missing, const_missing, const_unreadable = analyze(data, root)
    hbc = info["_hbc"]
    ss = set(hbc.strings)
    print(_t("== Build: %s (%s) ==", "== Build: %s (%s) ==") % (safe(os.path.basename(path)), safe(src)))
    print(_t("  Hermes bytecode version: %d · chuỗi: %d",
             "  Hermes bytecode version: %d · strings: %d") % (info["version"], info["string_count"]))
    print(_t("  v1 endpoint (api.fpt.edu.vn/.../MyFAP): %d", "  v1 endpoints: %d") % len(info["v1"]))
    print("    " + ", ".join(_sorted(info["v1"])))
    print(_t("  + survey.fpt.edu.vn: %s", "  + survey host: %s") % ", ".join(_sorted(info["survey"])) )
    print(_t("  v2 registry (MyFAP/<Name> + fap-proxy): %d", "  v2 registry: %d") % len(info["v2"]))
    if info["v2"]:
        print("    " + ", ".join(_sorted(info["v2"])))
    print(_t("  Host:", "  Hosts:"))
    for h in _sorted(info["hosts"]):
        print("    " + h)
    print(_t("  Marker:", "  Markers:"))
    for k, val in info["markers"].items():
        print("    %-18s %s" % (k, _t("CÓ", "yes") if val else _t("không", "no")))
    print(_t("  Hằng fap-cli trong bundle (chỉ CÓ/THIẾU):", "  fap-cli constants (present/missing only):"))
    _print_const_presence(consts, ss, hbc.strings)
    print(_t("  Endpoint fap-cli gọi: %d", "  Endpoints fap-cli calls: %d") % len(eps))
    if missing:
        print(_t("  ⚠️ fap-cli gọi nhưng THIẾU trong build: %s",
                 "  ⚠️ called by fap-cli but MISSING from build: %s") % ", ".join(safe(m) for m in missing))
    else:
        print(_t("  ✅ mọi endpoint fap-cli gọi đều có trong build",
                 "  ✅ every endpoint fap-cli calls is present"))
    # MỌI hằng fap-cli đọc được mà thiếu (không chỉ SECRET/BASE) => exit 1: LOGIN_PREFIX/CLIENT_ID/ISSUER/
    # REDIRECT_URI đổi là `fap login` hỏng y như đổi SECRET.
    _warn_consts(const_missing, const_unreadable, "build")
    changed = bool(missing) or bool(const_missing) or bool(const_unreadable)
    return 1 if changed else 0


def report_diff(old_path, new_path, root=REPO_ROOT):
    od, osrc = load_bundle(old_path)
    nd, nsrc = load_bundle(new_path)
    oi = analyze(od, root)[0]
    ni, consts, eps, missing, const_missing, const_unreadable = analyze(nd, root)
    print(_t("== Diff: %s (%s)  ->  %s (%s) ==", "== Diff: %s (%s)  ->  %s (%s) ==")
          % (safe(os.path.basename(old_path)), safe(osrc), safe(os.path.basename(new_path)), safe(nsrc)))
    print(_t("  version %d -> %d · chuỗi %d -> %d", "  version %d -> %d · strings %d -> %d")
          % (oi["version"], ni["version"], oi["string_count"], ni["string_count"]))

    def _diff(title, a, b):
        added = sorted(b - a)
        removed = sorted(a - b)
        print("  " + title)
        print(_t("    + thêm:  ", "    + added:   ") + (", ".join(safe(x) for x in added) if added else "-"))
        print(_t("    - bỏ:    ", "    - dropped: ") + (", ".join(safe(x) for x in removed) if removed else "-"))

    _diff(_t("v1 endpoint (case-SENSITIVE):", "v1 endpoints (case-SENSITIVE):"), oi["v1"], ni["v1"])
    _diff(_t("survey:", "survey:"), oi["survey"], ni["survey"])
    _diff(_t("v2 registry:", "v2 registry:"), oi["v2"], ni["v2"])
    _diff(_t("host:", "hosts:"), oi["hosts"], ni["hosts"])
    # Marker đổi
    print(_t("  Marker đổi:", "  Marker changes:"))
    any_marker = False
    for k in ni["markers"]:
        if oi["markers"].get(k) != ni["markers"][k]:
            any_marker = True
            print("    %-18s %s -> %s" % (k, oi["markers"].get(k), ni["markers"][k]))
    if not any_marker:
        print("    -")
    # Literal dạng khoá MỚI (chỉ đếm + độ dài, KHÔNG giá trị)
    old_secrets = {s for s in oi["_hbc"].strings if _looks_secret(s)}
    new_secrets = {s for s in ni["_hbc"].strings if _looks_secret(s)}
    fresh = new_secrets - old_secrets
    lens = sorted(len(s) for s in fresh)
    print(_t("  Literal 'dạng khoá' MỚI: %d (độ dài: %s)", "  New key-like literals: %d (lengths: %s)")
          % (len(fresh), ", ".join(str(x) for x in lens) if lens else "-"))
    # Hằng fap-cli trong build MỚI
    ss = set(ni["_hbc"].strings)
    print(_t("  Hằng fap-cli trong build MỚI (CÓ/THIẾU):", "  fap-cli constants in NEW build (present/missing):"))
    _print_const_presence(consts, ss, ni["_hbc"].strings)
    if missing:
        print(_t("  ⚠️ fap-cli gọi nhưng THIẾU ở build mới: %s",
                 "  ⚠️ called by fap-cli but MISSING in new build: %s") % ", ".join(safe(m) for m in missing))
    else:
        print(_t("  ✅ mọi endpoint fap-cli gọi đều có ở build mới",
                 "  ✅ every endpoint fap-cli calls is present in new build"))
    _warn_consts(const_missing, const_unreadable, _t("build mới", "new build"))
    changed = bool(missing) or bool(const_missing) or bool(const_unreadable)
    return 1 if changed else 0


# ---------------------------------------------------------------------------
# --write-v2-key: tìm khoá HMAC v2 THEO CẤU TRÚC, ghi vào .env (không in giá trị).
# ---------------------------------------------------------------------------
def find_v2_key(data):
    """Tìm hằng chuỗi dùng làm KHOÁ HmacSHA256 trong hàm checksum v2.

    Trả (key, 'ok') nếu đúng MỘT ứng viên; (None, lý_do) nếu 0 hoặc >1.
    Hàm checksum v2 = hàm tham chiếu identifier 'HmacSHA256' VÀ nạp hằng '%3d' (mã hoá checksum
    '='→'%3d'); khoá = hằng LoadConstString 'dạng khoá' (hex≥12 có chữ số) trong hàm đó.
    Cần hermes-dec (thư viện) hoặc hbc-disassembler (CLI). KHÔNG in giá trị.
    """
    funcs = _decode_functions(data)
    if funcs is None:
        return None, _t("cần hermes-dec hoặc hbc-disassembler để đọc bytecode",
                        "hermes-dec or hbc-disassembler required to read bytecode")
    if isinstance(funcs, DecodeFailed):          # công cụ CÓ nhưng decode lỗi — KHÁC "thiếu công cụ"
        return None, _t("%s không decode được bytecode (%s) — build hỏng/cắt cụt hoặc công cụ chưa hỗ trợ bản này",
                        "%s failed to decode the bytecode (%s) — corrupt/truncated build or unsupported by the tool") \
            % (funcs.tool, funcs.error)
    cand_keys = set()
    cand_funcs = 0
    for id_refs, const_strs in funcs:
        if "HmacSHA256" in id_refs and "%3d" in const_strs:
            keys = {s for s in const_strs if _looks_secret(s)}
            if keys:
                cand_funcs += 1
                cand_keys |= keys
    if cand_funcs == 0 or not cand_keys:
        return None, _t("không thấy hàm checksum v2 (không có khoá v2 — đúng với bản chưa có v2)",
                        "no v2 checksum function found (no v2 key — expected for pre-v2 builds)")
    if cand_funcs > 1 or len(cand_keys) > 1:
        return None, _t("nhiều ứng viên khoá (%d hàm, %d khoá) — từ chối",
                        "multiple key candidates (%d funcs, %d keys) — refusing") % (cand_funcs, len(cand_keys))
    return next(iter(cand_keys)), "ok"


class DecodeFailed(object):
    """Marker: công cụ decode CÓ nhưng lỗi khi đọc bundle (khác None = KHÔNG có công cụ nào).

    Chỉ giữ TÊN lớp lỗi — message của parser/subprocess có thể chứa byte của input hay đường dẫn tạm."""

    def __init__(self, tool, error):
        self.tool = tool
        self.error = error


def _decode_functions(data):
    """Trả list [(set id_refs, set const_strings)] mỗi function; None nếu KHÔNG có công cụ nào;
    DecodeFailed nếu có công cụ nhưng decode lỗi.

    Ưu tiên hermes-dec (thư viện, nhanh, trong bộ nhớ); không có / lỗi -> hbc-disassembler CLI ra
    thư mục tạm rồi parse text, XOÁ ngay sau đó (không bao giờ giữ lại .hasm chứa PID/PII)."""
    out = _decode_with_hermes_dec(data)
    if isinstance(out, list):
        return out
    cli = _decode_with_cli(data)
    if isinstance(cli, list):
        return cli
    # Cả hai không ra kết quả: ưu tiên báo lỗi THẬT của hermes-dec, rồi lỗi CLI, cuối cùng None (thiếu công cụ).
    return out if out is not None else cli


def _decode_with_hermes_dec(data):
    try:
        import io as _io
        from hermes_dec.parsers.hbc_file_parser import HBCReader
        from hermes_dec.parsers.hbc_bytecode_parser import parse_hbc_bytecode
        from hermes_dec.parsers.hbc_opcodes.def_classes import OperandMeaning
    except Exception:
        return None                  # KHÔNG có thư viện -> None (chỉ trường hợp này)
    try:
        reader = HBCReader()
        buf = _io.BytesIO(data)      # giữ buffer MỞ suốt quá trình decode (parser seek lại nhiều lần)
        reader.read_whole_file(buf)
        out = []
        for fh in reader.function_headers:
            id_refs = set()
            const_strs = set()
            for ins in parse_hbc_bytecode(fh, reader):
                name = ins.inst.name
                for idx, op in enumerate(ins.inst.operands):
                    if op.operand_meaning == OperandMeaning.string_id:
                        sid = getattr(ins, "arg%d" % (idx + 1))
                        try:
                            val = reader.strings[sid]
                        except (IndexError, TypeError):
                            continue
                        if name.startswith("LoadConstString"):
                            const_strs.add(val)
                        elif name.startswith("GetById") or name.startswith("TryGetById") or name == "GetByIdShort":
                            id_refs.add(val)
            out.append((id_refs, const_strs))
        return out
    except Exception as e:           # parser vỡ (assert/struct/index… trên build hỏng) -> marker, KHÔNG traceback
        return DecodeFailed("hermes-dec", type(e).__name__)


def _decode_with_cli(data):
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which("hbc-disassembler")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="apk_drift_")
    try:
        bundle_path = os.path.join(tmp, "b.bundle")
        hasm_path = os.path.join(tmp, "b.hasm")
        with open(bundle_path, "wb") as f:
            f.write(data)
        subprocess.run([exe, bundle_path, hasm_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return _parse_hasm_functions(hasm_path)
    except Exception as e:           # CÓ công cụ nhưng lỗi -> marker (trước đây trả None = báo nhầm "cần công cụ")
        return DecodeFailed("hbc-disassembler", type(e).__name__)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)   # XOÁ .hasm (chứa PII) ngay — MỌI đường, kể cả lỗi/Ctrl-C


_HASM_STR = re.compile(r"# String: '((?:[^'\\]|\\.)*)' \((Identifier|String)\)")
_HASM_INST = re.compile(r"<([A-Za-z0-9]+)>")


def _parse_hasm_functions(hasm_path):
    out = []
    id_refs = set()
    const_strs = set()
    started = False
    with open(hasm_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("=> ["):
                if started:
                    out.append((id_refs, const_strs))
                id_refs, const_strs = set(), set()
                started = True
                continue
            mi = _HASM_INST.search(line)
            ms = _HASM_STR.search(line)
            if not mi or not ms:
                continue
            name, (val, kind) = mi.group(1), (ms.group(1), ms.group(2))
            val = val.encode().decode("unicode_escape", errors="replace") if "\\" in val else val
            if name.startswith("LoadConstString"):
                const_strs.add(val)
            elif name.startswith("GetById") or name.startswith("TryGetById") or name == "GetByIdShort":
                id_refs.add(val)
    if started:
        out.append((id_refs, const_strs))
    return out


# ---------------------------------------------------------------------------
# Ghi .env: thay/append FAP_V2_KEY, GIỮ NGUYÊN từng byte mọi dòng khác, chmod 0600, atomic.
# KHÔNG in giá trị — chỉ in độ dài + sha256[:8].
# ---------------------------------------------------------------------------
# Tách dòng ĐÚNG như loader .env của fapc (đọc text mode = universal newlines: \r\n, \r, \n) và GIỮ dấu
# xuống dòng. KHÔNG dùng splitlines(): nó tách cả \x0b \x0c \x1c-\x1e \x85     -> cắt giá trị.
_EOL = re.compile(r"(\r\n|\r|\n)")


def _open_private(path):
    """Mở file tạm để GHI: quyền 0600 ngay lúc tạo (không qua umask rộng), KHÔNG theo symlink (O_NOFOLLOW nếu có).

    FS không có quyền kiểu POSIX làm os.open lỗi -> lùi về open() thường, nhưng KHÔNG BAO GIỜ khi path là
    symlink (lùi ở đó = đi theo symlink, chính thứ O_NOFOLLOW chặn)."""
    flags = (os.O_WRONLY | os.O_CREAT | os.O_TRUNC
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))   # O_BINARY: Windows không đổi \n
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as e:
        if e.errno == errno.ELOOP or os.path.islink(path):
            raise
        return open(path, "w", encoding="utf-8", newline="")
    try:
        return os.fdopen(fd, "w", encoding="utf-8", newline="")
    except BaseException:
        os.close(fd)
        raise


def _env_with_key(text, key):
    """THUẦN: nội dung .env mới — thay dòng FAP_V2_KEY ĐẦU TIÊN (loader lấy giá trị đầu) hoặc append.
    Mọi byte khác giữ nguyên; dòng thay giữ đúng kiểu xuống dòng của nó; append theo kiểu của file."""
    parts = _EOL.split(text)                     # [dòng, eol, dòng, eol, …, dòng_cuối]
    for i in range(0, len(parts), 2):
        if parts[i].split("=", 1)[0].strip() == "FAP_V2_KEY":
            parts[i] = "FAP_V2_KEY=" + key
            return "".join(parts)
    eol = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += eol                              # dòng cuối chưa có xuống dòng -> thêm trước khi append
    return text + "FAP_V2_KEY=" + key + eol


def write_v2_key(env_path, key):
    text = ""
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8", newline="") as f:     # newline="" = KHÔNG dịch \r\n
            text = f.read()
    out = _env_with_key(text, key)
    # tmp RIÊNG mỗi tiến trình, tạo 0600 + không theo symlink; lỗi giữa chừng -> XOÁ tmp (nó chứa CẢ .env + khoá).
    tmp = f"{env_path}.{os.getpid()}.tmp"
    try:
        with _open_private(tmp) as f:
            f.write(out)
        try:
            os.chmod(tmp, 0o600)                 # nhánh lùi open() thường: siết lại trước khi thay
        except OSError:
            pass
        os.replace(tmp, env_path)                # atomic
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass


def cmd_write_v2_key(path, env_file):
    data, _src = load_bundle(path)
    # Kiểm magic / version / cắt cụt bằng bộ đọc của CHÍNH tool trước khi đưa cho decoder ngoài:
    # input hỏng -> HBCError rõ ràng (main -> exit 2), không phải traceback từ sâu trong hermes-dec.
    HBC(data)
    secret_consts = fapcli_constants()
    key, reason = find_v2_key(data)
    if key is None:
        sys.stderr.write(_t("Từ chối: %s\n", "Refused: %s\n") % reason)
        return 2
    # Sanity: khoá v2 PHẢI khác secret HMAC v1 và tiền tố login (so boolean, không in).
    if key == secret_consts.get("SECRET") or key == secret_consts.get("LOGIN_PREFIX"):
        sys.stderr.write(_t("Từ chối: ứng viên trùng secret v1 / tiền tố login\n",
                            "Refused: candidate equals v1 secret / login prefix\n"))
        return 2
    env_path = env_file or os.path.join(REPO_ROOT, ".env")
    try:
        write_v2_key(env_path, key)
    except (OSError, ValueError) as e:           # quyền/khoá file, .env không phải UTF-8… — chỉ TÊN lớp lỗi
        sys.stderr.write(_t("Lỗi: không ghi được file env (%s)\n", "Error: could not write the env file (%s)\n")
                         % type(e).__name__)
        return 2
    sha8 = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    print(_t("FAP_V2_KEY đã ghi (%d ký tự, sha256 %s)", "FAP_V2_KEY written (%d chars, sha256 %s)")
          % (len(key), sha8))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Offline APK/bundle drift checker for fap-cli.")
    p.add_argument("builds", nargs="*", help="1 build (kiểm) hoặc 2 build (diff)")
    p.add_argument("--write-v2-key", metavar="BUILD", dest="write_v2_key",
                   help=_t("tìm khoá HMAC v2 theo cấu trúc rồi ghi FAP_V2_KEY vào .env",
                           "find the v2 HMAC key structurally and write FAP_V2_KEY to .env"))
    p.add_argument("--env-file", help=_t("file .env đích (mặc định: .env gốc repo)",
                                         "target .env file (default: repo-root .env)"))
    args = p.parse_args(argv)
    try:
        if args.write_v2_key:
            return cmd_write_v2_key(args.write_v2_key, args.env_file)
        if len(args.builds) == 1:
            return report_one(args.builds[0])
        if len(args.builds) == 2:
            return report_diff(args.builds[0], args.builds[1])
        p.error(_t("cần 1 build (kiểm) hoặc 2 build (diff), hoặc --write-v2-key",
                   "need 1 build (check) or 2 builds (diff), or --write-v2-key"))
    except HBCError as e:
        sys.stderr.write(_t("Lỗi: %s\n", "Error: %s\n") % e)
        return 2
    except _INPUT_ERRORS as e:
        # APK/bundle hỏng hoặc cắt cụt: exit 2 (lỗi đầu vào) — KHÔNG để traceback ra exit 1 (= "có drift").
        # Chỉ in TÊN lớp lỗi: message của zipfile/struct/codec có thể chứa byte của input (bundle có PII).
        sys.stderr.write(_t("Lỗi: đầu vào hỏng/cắt cụt hoặc không đọc được (%s)\n",
                            "Error: corrupt/truncated or unreadable input (%s)\n") % type(e).__name__)
        return 2


# Lỗi từ input hỏng: zip hỏng/CRC/deflate (BadZipFile, zlib.error, EOFError), zip mã hoá / nén lạ
# (RuntimeError, NotImplementedError), bảng HBC lệch (struct.error, IndexError), I/O (OSError), codec.
_INPUT_ERRORS = (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, struct.error, UnicodeDecodeError,
                 EOFError, IndexError, OSError, ValueError, RuntimeError)


if __name__ == "__main__":
    sys.exit(main())
