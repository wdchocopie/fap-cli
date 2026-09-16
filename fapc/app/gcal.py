#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcal.py — Đẩy thời khóa biểu lên GOOGLE CALENDAR qua OAuth (Calendar API).

Khác với .ics (import thủ công), cái này TỰ ĐỒNG BỘ: chạy lại = cập nhật, không tạo trùng
(dedup theo iCalUID). Có thể đặt lịch chạy định kỳ.

Cài thư viện Google (1 lần):
    pip install -e ".[gcal]"      # hoặc: pip install -r requirements-gcal.txt

Chuẩn bị credentials (1 lần):
    Google Cloud Console → tạo project → bật "Google Calendar API" →
    OAuth consent screen (External, thêm chính bạn vào Test users) →
    Credentials → Create OAuth client ID → loại "Desktop app" → tải JSON → lưu thành
    <gốc repo>/credentials.json

Chạy (từ gốc repo):
    fap calendar-auth     # đăng nhập Google 1 lần (DÁN URL redirect) -> output/gcal_token.json
    fap calendar-sync     # đẩy/cập nhật lịch hiện tại lên Google Calendar

Chỉ xin quyền GHI SỰ KIỆN (calendar.events). Token Google lưu output/gcal_token.json
(FAP_PROFILE=alice -> output/profiles/alice/gcal_token.json) — ĐỪNG commit.

────────────────────────────────────────────────────────────────────────────────────────────
NHIỀU ĐÍCH ĐẾN (multi-Google) — 1 tài khoản FAP đẩy sang NHIỀU lịch/nhiều tài khoản Google.
Mỗi đích có một NHÃN (label). Nhãn RỖNG "" = đích mặc định như xưa (token gcal_token.json +
GCAL_CALENDAR_ID). Nhãn có tên -> token riêng output/gcal/<nhãn>.json, calendar_id đăng ký ở
output/gcal/destinations.json. Xem `_token_file` / `_calendar_id` / `add_destination`.

NHIỀU TÀI KHOẢN (multi-profile): mọi sự kiện fap-cli tạo đều mang DẤU CHỦ SỞ HỮU = mã sinh viên
(iCalUID + nhãn riêng `fapc_owner`). Nhờ vậy hai người dùng chung 1 Google Calendar KHÔNG bao giờ
dọn (prune) trúng sự kiện của nhau. Xem `_owner()` / `_uids_for()` bên dưới.

⚠️ CHỐT AN TOÀN: hai nhãn KHÔNG được trỏ vào CÙNG một calendar_id cụ thể. `fapc_owner` gắn theo
MÃ SV (giống nhau cho mọi nhãn của cùng 1 FAP), nên hai nhãn chung 1 lịch sẽ sinh iCalUID trùng
(ghi đè nhau) và prune nhãn này XÓA sự kiện nhãn kia. `_check_no_dupe()` từ chối trước khi kịp hại.
"""
import json, os, re, sys
from ..core.api import creds, current_semester
from ..core.schedule import fetch_sessions, parse_session  # tái dùng parser ngày/giờ
from ..core import paths
from ..i18n import t
from .. import config, fmt

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRED_FILE  = os.path.join(ROOT, "credentials.json")   # credential của ỨNG DỤNG (dùng chung mọi profile) → ở gốc repo
DEFAULT_TOKEN = paths.out("gcal_token.json")          # token của đích MẶC ĐỊNH ("") → theo profile
TOKEN_FILE = DEFAULT_TOKEN                             # tên cũ, giữ cho tương thích ngược
GCAL_DIR   = paths.out("gcal")                         # token + sổ đăng ký của các đích CÓ NHÃN
REGISTRY   = paths.out("gcal", "destinations.json")    # {nhãn: {"calendar_id": …}}
OAUTH_STATE = paths.out(".gcal_oauth.json")            # phiên OAuth đang dở (loopback-paste): {state, label}

# Loopback cho DESKTOP CLIENT: đăng nhập xong Google chuyển tới http://127.0.0.1/?...&code=… — không có
# server nào lắng ở đó nên trình duyệt báo "không kết nối được" (BÌNH THƯỜNG); người dùng COPY URL rồi DÁN.
# Không cần mở cổng, chạy được trên máy chủ không màn hình. Khác run_local_server (đòi mở browser tại chỗ).
REDIRECT_URI = "http://127.0.0.1"

# Tên nhãn: chữ/số/._- ; chặn '..' và dấu phân cách (không cho thoát ra ngoài gcal/). "destinations" bị
# cấm vì trùng tên file sổ đăng ký (output/gcal/destinations.json). Các TỪ KHOÁ CỜ của parse_sync_args
# (prune/yes/force + bí danh tiếng Việt) cũng bị cấm: nếu một đích tên "prune" thì "/calendar-prune prune"
# không phân biệt được đó là nhãn hay cờ ⇒ prune nhầm calendar mặc định. Cấm ở nguồn cho khỏi mơ hồ.
_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_RESERVED_LABELS = frozenset({
    ".", "..", "destinations", "gcal_token",
    "prune", "dọn", "don", "yes", "có", "co", "force", "ép", "ep",
})


# ───────────────────────── NHÃN + SỔ ĐĂNG KÝ ĐÍCH ĐẾN ─────────────────────────
def norm_label(label):
    """THUẦN: nhãn đã làm sạch. Rỗng/None -> "" (đích mặc định). Tên KHÔNG hợp lệ -> raise ValueError
    (KHÔNG lặng lẽ rơi về mặc định: người dùng gõ 'wörk' mà ghi vào đích mặc định thì rất khó hiểu)."""
    s = (label or "").strip()
    if not s:
        return ""
    if s in _RESERVED_LABELS or not _LABEL_RE.match(s):
        raise ValueError(t(
            f"Nhãn '{s}' không hợp lệ — chỉ dùng chữ/số/._- (và không phải 'destinations').",
            f"Label '{s}' is invalid — use letters/digits/._- only (and not 'destinations')."))
    return s


def _token_file(label):
    """Đường token của một đích. Nhãn rỗng -> gcal_token.json như cũ (tương thích ngược, KHÔNG migrate)."""
    label = norm_label(label)
    return DEFAULT_TOKEN if not label else paths.out("gcal", f"{label}.json")


def _load_registry():
    """Sổ đăng ký đích có nhãn: {nhãn: {"calendar_id": …}}. Không có / hỏng -> {} (KHÔNG raise).
    BỎ mục có value KHÔNG phải dict (sổ bị sửa tay / ghi dở / định dạng tương lai) — nếu không, chỗ
    `ent.get("calendar_id")` sẽ ném AttributeError chưa bắt và làm SẬP bot ở /calendar-list."""
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _save_registry(reg):
    paths.ensure_dir(REGISTRY)
    tmp = f"{REGISTRY}.{os.getpid()}.tmp"                  # ghi nguyên tử (tránh cụt file lúc bị ngắt)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, REGISTRY)


def _calendar_id(label):
    """calendar_id của một đích. Nhãn rỗng -> GCAL_CALENDAR_ID (env, mặc định 'primary').
    Nhãn có tên nhưng CHƯA đăng ký -> raise SystemExit (bảo người dùng calendar-add trước)."""
    label = norm_label(label)
    if not label:
        return config.GCAL_CALENDAR_ID
    ent = _load_registry().get(label)
    if not ent or not ent.get("calendar_id"):
        raise SystemExit(t(
            f"Đích '{label}' chưa đăng ký calendar_id. Chạy: fap calendar-add {label} <calendar_id>",
            f"Destination '{label}' has no calendar_id yet. Run: fap calendar-add {label} <calendar_id>"))
    return str(ent["calendar_id"])


def _all_targets():
    """THUẦN-ish (đọc registry+env): {nhãn: calendar_id} cho MỌI đích, gồm cả đích mặc định "".
    Dùng để phát hiện hai nhãn trỏ trùng một lịch. BỎ QUA khóa hỏng (sổ bị sửa tay) — không được để
    một dòng sổ lỗi làm sập lệnh calendar-list trong bot."""
    out = {"": config.GCAL_CALENDAR_ID}
    for label, ent in _load_registry().items():
        try:
            label = norm_label(label)
        except ValueError:
            continue
        if not label:
            continue
        cid = (ent or {}).get("calendar_id")
        if cid:
            out[label] = str(cid)
    return out


def _norm_cid(cal_id):
    """THUẦN: calendar_id chuẩn hoá để SO SÁNH — id lịch (email / …@group.calendar.google.com) không
    phân biệt hoa-thường và không tính khoảng trắng bao quanh, nên 'Me@Gmail.com' == ' me@gmail.com '."""
    return str(cal_id or "").strip().lower()


def _is_concrete(cal_id):
    """calendar_id có phải một lịch CỤ THỂ (so chuỗi được) không? 'primary' là TƯƠNG ĐỐI theo tài khoản
    (mỗi tài khoản Google có 'primary' RIÊNG) nên hai nhãn cùng 'primary' ở HAI tài khoản là hai lịch
    KHÁC nhau — không coi là trùng. Mọi id khác (email / …@group.calendar.google.com) là cụ thể."""
    return _norm_cid(cal_id) not in ("", "primary")


def _dupe_of(label, targets=None):
    """THUẦN: danh sách nhãn KHÁC đang trỏ vào CÙNG calendar_id cụ thể với `label` ([] nếu an toàn).
    So sánh KHÔNG phân biệt hoa-thường (xem `_norm_cid`); chỉ xét id cụ thể — 'primary' ở nhiều tài khoản
    là hợp lệ."""
    targets = _all_targets() if targets is None else targets
    label = norm_label(label)
    mine = targets.get(label)
    if not _is_concrete(mine):
        return []
    return [l for l, cid in targets.items() if l != label and _norm_cid(cid) == _norm_cid(mine)]


def _check_no_dupe(label):
    """Chặn trước khi sync/prune: nếu `label` chung một lịch cụ thể với nhãn khác thì TỪ CHỐI —
    prune sẽ xóa chéo và import sinh iCalUID trùng (xem docstring đầu file)."""
    dup = _dupe_of(label)
    if dup:
        cid = _all_targets().get(norm_label(label))
        raise SystemExit(t(
            f"⛔ Đích '{label or 'mặc định'}' dùng CHUNG lịch {cid} với: {', '.join(d or 'mặc định' for d in dup)}. "
            "Hai đích chung một lịch sẽ xóa chéo sự kiện của nhau — hãy đổi calendar_id cho khác nhau.",
            f"⛔ Destination '{label or 'default'}' shares calendar {cid} with: {', '.join(d or 'default' for d in dup)}. "
            "Two destinations on one calendar would prune each other's events — give them distinct calendar_ids."))


def add_destination(label, calendar_id):
    """Đăng ký một đích CÓ NHÃN với calendar_id CỤ THỂ. Trả chuỗi kết quả (không raise cho lỗi người dùng).

    BẮT một calendar_id cụ thể (email chính hoặc …@group.calendar.google.com), KHÔNG nhận 'primary' cho
    nhãn có tên: nhờ vậy so-chuỗi phát hiện trùng lịch là ĐỦ và ĐÚNG (xem `_is_concrete`). Lịch primary
    của một tài khoản có id = chính địa chỉ email của tài khoản đó."""
    try:
        label = norm_label(label)
    except ValueError as e:
        return "⛔ " + str(e)
    if not label:
        return t("Đích mặc định (nhãn rỗng) dùng GCAL_CALENDAR_ID trong .env — không đăng ký ở đây.",
                 "The default destination (empty label) uses GCAL_CALENDAR_ID in .env — not registered here.")
    cid = str(calendar_id or "").strip()
    if not cid or not _is_concrete(cid):
        return t("Cần calendar_id CỤ THỂ (email của tài khoản, hoặc …@group.calendar.google.com) — không phải 'primary'. "
                 "Mở Google Calendar → Cài đặt lịch → 'ID lịch'.",
                 "Need a CONCRETE calendar_id (the account's email, or …@group.calendar.google.com) — not 'primary'. "
                 "Find it in Google Calendar → Settings for that calendar → 'Calendar ID'.")
    targets = dict(_all_targets()); targets[label] = cid
    dup = _dupe_of(label, targets)
    if dup:
        return t(f"⛔ calendar_id {cid} đã được nhãn '{', '.join(d or 'mặc định' for d in dup)}' dùng — "
                 "mỗi đích phải là một lịch khác nhau (tránh xóa chéo).",
                 f"⛔ calendar_id {cid} is already used by '{', '.join(d or 'default' for d in dup)}' — "
                 "each destination must be a distinct calendar (avoids cross-prune).")
    reg = _load_registry(); reg[label] = {"calendar_id": cid}
    try:
        _save_registry(reg)
    except OSError as e:                                   # đĩa lỗi/chỉ-đọc: trả CHỮ, KHÔNG để ném ra vòng lặp bot
        return t(f"⛔ Không ghi được sổ đích: {e}", f"⛔ Could not write destination registry: {e}")
    authed = os.path.exists(_token_file(label))
    tail = t("Đã có token Google.", "Google token present.") if authed \
        else t(f"Chưa xác thực — chạy: fap calendar-auth {label}", f"Not authorized yet — run: fap calendar-auth {label}")
    return t(f"✓ Đăng ký đích '{label}' → {cid}. {tail}", f"✓ Registered destination '{label}' → {cid}. {tail}")


def remove_destination(label):
    """Bỏ đăng ký một đích: xóa mục trong sổ + token của nó. KHÔNG đụng sự kiện đã đẩy (muốn dọn thì
    calendar-prune TRƯỚC khi remove). Trả chuỗi kết quả."""
    try:
        label = norm_label(label)
    except ValueError as e:
        return "⛔ " + str(e)
    if not label:
        return t("Không thể bỏ đích mặc định.", "Cannot remove the default destination.")
    reg = _load_registry()
    existed = label in reg
    reg.pop(label, None)
    try:
        _save_registry(reg)
    except OSError as e:
        return t(f"⛔ Không ghi được sổ đích: {e}", f"⛔ Could not write destination registry: {e}")
    tok = _token_file(label)
    try:
        os.remove(tok)
    except OSError:
        pass
    if not existed:
        return t(f"(Đích '{label}' vốn chưa đăng ký.)", f"(Destination '{label}' was not registered.)")
    return t(f"✓ Đã bỏ đích '{label}' (sự kiện đã đẩy vẫn còn — prune trước nếu muốn dọn).",
             f"✓ Removed destination '{label}' (pushed events remain — prune first if you want them gone).")


def list_destinations():
    """[(nhãn, calendar_id, đã_xác_thực?, cảnh_báo_trùng?)] cho mọi đích, đích mặc định "" đứng đầu."""
    targets = _all_targets()
    order = [""] + sorted(l for l in targets if l)
    rows = []
    for label in order:
        rows.append((label, targets[label], os.path.exists(_token_file(label)), bool(_dupe_of(label, targets))))
    return rows


def destinations_text():
    """Bảng đích cho chat/CLI."""
    rows = list_destinations()
    lines = [fmt.header("📆", t("Đích Google Calendar", "Google Calendar destinations"))]
    for label, cid, authed, dup in rows:
        name = label or t("(mặc định)", "(default)")
        mark = "✅" if authed else "🔒"
        warn = " ⚠️" + t("TRÙNG LỊCH", "SHARED CAL") if dup else ""
        lines.append(f"{mark} {name} → {cid}{warn}")
    lines.append("")
    lines.append(t("✅ đã xác thực · 🔒 chưa (calendar-auth <nhãn>)",
                   "✅ authorized · 🔒 not yet (calendar-auth <label>)"))
    return "\n".join(lines)


# ───────────────────────── OAUTH (loopback-paste, không cần browser tại chỗ) ─────────────────────────
def _missing_libs(extra=""):
    return SystemExit(t(
        "Thiếu thư viện Google. Cài: pip install google-api-python-client google-auth-oauthlib" + extra,
        "Missing Google libs. Install: pip install google-api-python-client google-auth-oauthlib" + extra))


def _require_cred():
    if not os.path.exists(CRED_FILE):
        raise SystemExit(t(
            f"Thiếu {CRED_FILE}. Tạo OAuth client 'Desktop app' trên Google Cloud (bật Calendar API), "
            "tải credentials.json về gốc repo.",
            f"Missing {CRED_FILE}. Create a 'Desktop app' OAuth client on Google Cloud (enable Calendar API), "
            "download credentials.json to the repo root."))


def gcal_auth_url(label=""):
    """Bước 1 của đăng nhập Google (loopback-paste): trả URL để người dùng mở + đăng nhập. KHÔNG mở
    browser, KHÔNG in token. Lưu {state, label} vào OAUTH_STATE để bước 2 khớp lại. Trả (url, label)."""
    label = norm_label(label)
    if label:                                             # nhãn có tên PHẢI đăng ký calendar_id trước
        _calendar_id(label)                               # raise SystemExit nếu chưa add
    _require_cred()
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise _missing_libs()
    flow = Flow.from_client_secrets_file(CRED_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    # access_type=offline + prompt=consent -> BẮT BUỘC có refresh_token (nếu không, token hết hạn là phải
    # đăng nhập lại thủ công — vô dụng cho bot chạy nền).
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _write_state({"state": state, "label": label})
    return url, label


def gcal_auth_finish(pasted, label=None):
    """Bước 2: đổi URL redirect người dùng dán -> token Google, lưu theo nhãn. Trả chuỗi kết quả.
    TUYỆT ĐỐI không in/không trả token ra ngoài. `label=None` -> lấy nhãn từ phiên đã lưu."""
    st = _read_state()
    if not st or not st.get("state"):
        raise SystemExit(t("Chưa mở phiên xác thực Google — chạy calendar-auth trước.",
                           "No Google auth in progress — run calendar-auth first."))
    label = norm_label(st.get("label", "")) if label is None else norm_label(label)
    if label != norm_label(st.get("label", "")):
        raise SystemExit(t("Nhãn không khớp phiên đang mở — chạy calendar-auth lại.",
                           "Label does not match the pending session — run calendar-auth again."))
    _require_cred()
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise _missing_libs()
    # OAUTHLIB_INSECURE_TRANSPORT: redirect http://127.0.0.1 (không TLS) sẽ bị oauthlib chặn nếu không bật.
    # RELAX_TOKEN_SCOPE: Google đôi khi trả tập scope KHÁC (thêm scope đã cấp trước) -> khỏi nổ "Scope changed".
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow = Flow.from_client_secrets_file(CRED_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI,
                                         state=st["state"])
    try:
        flow.fetch_token(authorization_response=str(pasted or "").strip())
    except Exception as e:                                # noqa: BLE001 — lỗi nào cũng phải thành CHỮ cho chat
        raise SystemExit(t(f"Đổi mã Google thất bại: {type(e).__name__}. Dán ĐÚNG cả URL redirect, hoặc calendar-auth lại.",
                           f"Google token exchange failed: {type(e).__name__}. Paste the FULL redirect URL, or calendar-auth again."))
    creds_ = flow.credentials
    if not getattr(creds_, "refresh_token", None):
        raise SystemExit(t("Google không cấp refresh_token (thu hồi quyền cũ ở myaccount.google.com rồi thử lại).",
                           "Google returned no refresh_token (revoke prior access at myaccount.google.com, then retry)."))
    _save(creds_, _token_file(label))
    _clear_state()
    where = label or t("mặc định", "default")
    return t(f"✅ Đã xác thực Google cho đích '{where}'.", f"✅ Google authorized for destination '{where}'.")


def _write_state(obj):
    _atomic_write_600(OAUTH_STATE, json.dumps(obj))        # chứa nonce CSRF + nhãn: siết 0600 như token


def _read_state():
    try:
        with open(OAUTH_STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _clear_state():
    try:
        os.remove(OAUTH_STATE)
    except OSError:
        pass


def looks_like_gredirect(text):
    """THUẦN: tin này có vẻ là URL redirect loopback của Google không? (bot dùng để XOÁ NGAY tin đó).

    Phải nhận diện TRƯỚC `auth.looks_like_redirect` của FAP: URL Google là http://127.0.0.1/?...&code=…
    cũng khớp mẫu FAP (có 'http' + 'code=') nên nếu không tách bằng host 127.0.0.1/localhost thì tin
    Google sẽ bị định tuyến nhầm sang luồng đăng nhập FAP. 'error=' cũng nhận (Google trả lỗi về đúng URL).

    Cũng nhận MÃ TRẦN dạng '4/...' (người dùng chỉ copy mỗi code thay vì cả URL, trái hướng dẫn): mã uỷ
    quyền Google luôn bắt đầu bằng '4/'. Nhận để XOÁ NGAY tin đó (bước đổi mã sau sẽ báo 'dán cả URL')."""
    s = str(text or "")
    if s.strip().startswith("4/"):                         # mã Google trần, không kèm URL -> vẫn phải xoá
        return True
    if "127.0.0.1" not in s and "localhost" not in s:
        return False
    return ("code=" in s) or ("error=" in s)


# ───────────────────────── CREDS + SERVICE (theo nhãn) ─────────────────────────
def _load_creds(label=""):
    """Token của một đích, tự refresh nếu hết hạn. CHỈ refresh, KHÔNG mở browser — luồng xác thực thật
    là loopback-paste (gcal_auth_url/gcal_auth_finish). Chưa có/không refresh được -> SystemExit sạch."""
    token_file = _token_file(label)
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise _missing_libs()
    creds_ = None
    if os.path.exists(token_file):
        try: creds_ = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception: creds_ = None
    if creds_ and creds_.valid:
        return creds_
    if creds_ and creds_.expired and creds_.refresh_token:
        try:
            from google.auth.exceptions import RefreshError
        except ImportError:
            RefreshError = Exception
        try:
            creds_.refresh(Request())
        except RefreshError as e:                          # CHỈ token hết hạn/thu hồi (KHÁC lỗi mạng tạm thời → để propagate)
            raise SystemExit(t(
                f"Token Google không refresh được ({type(e).__name__}). Chạy: fap calendar-auth {label}".rstrip(),
                f"Google token could not refresh ({type(e).__name__}). Run: fap calendar-auth {label}".rstrip()))
        else:
            _save(creds_, token_file); return creds_       # refresh OK → lưu (ngoài try: lỗi _save không bị nhầm là lỗi refresh)
    where = f" {label}".rstrip()
    raise SystemExit(t(f"Chưa xác thực Google (đích '{label or 'mặc định'}'). Chạy: fap calendar-auth{where}",
                       f"Not authorized (destination '{label or 'default'}'). Run: fap calendar-auth{where}"))


def _atomic_write_600(path, text):
    """Ghi `text` vào `path` NGUYÊN TỬ và quyền 0600 NGAY TỪ ĐẦU. Mở tmp bằng os.open(...,0o600) như
    core/auth.py — KHÔNG dùng open() rồi chmod sau, vì giữa hai bước có cửa sổ file token đọc-được bởi
    user khác trên máy (umask thường 0644). Trên Windows mode gần như vô nghĩa, nhưng máy chủ là Linux."""
    paths.ensure_dir(path)                                  # thư mục profile / gcal/ có thể chưa tồn tại
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)                              # nguyên tử (khỏi cụt file lúc bị ngắt)
    except OSError:
        try: os.remove(tmp)
        except OSError: pass
        raise
    try: os.chmod(path, 0o600)                              # siết lại lần nữa nếu file đã tồn tại từ trước
    except OSError: pass


def _save(creds_, path=None):
    path = DEFAULT_TOKEN if path is None else path         # path=None: tương thích chữ ký cũ _save(creds_)
    _atomic_write_600(path, creds_.to_json())


def _service(label=""):
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=_load_creds(label), cache_discovery=False)

# ---------- DẤU CHỦ SỞ HỮU: mỗi sự kiện thuộc về ĐÚNG 1 mã sinh viên ----------
def _owner(roll):
    """THUẦN: mã sinh viên -> khóa chủ sở hữu an toàn cho iCalUID/nhãn (chữ thường, chỉ a-z0-9).

    Dùng MÃ SINH VIÊN (không phải tên profile): đó là danh tính THẬT của dữ liệu — đổi tên profile
    hay chạy cùng tài khoản ở máy khác vẫn ra cùng khóa, nên sự kiện không bị mồ côi/nhân đôi."""
    return re.sub(r"[^a-z0-9]", "", str(roll or "").lower()) or "unknown"

def _uids_for(session, owner):
    """THUẦN: (uid_MỚI có mã SV, uid_CŨ không có mã SV) của 1 buổi; None nếu buổi không parse được.

    uid CŨ là dạng fap-cli sinh ra TRƯỚC bản này — vẫn phải nhận ra để "nhận nuôi" (adopt) lịch cũ,
    nếu không mỗi sự kiện sẽ bị tạo lại lần 2 dưới uid mới."""
    p = parse_session(session)
    if not p:
        return None
    start = p[0]
    tail = f"{start.strftime('%Y%m%d')}-{session.get('subjectCode', 'Lớp')}-{session.get('slot','')}@fap.fpt.edu.vn"
    return f"fapc-{owner}-{tail}", f"fapc-{tail}"

def _pick_uid(session, owner, adopt):
    """THUẦN: uid THỰC SỰ dùng cho buổi này. Đã có sự kiện CỦA TÔI mang uid cũ trên lịch (`adopt`)
    → tái dùng uid cũ (cập nhật tại chỗ, KHÔNG nhân đôi, KHÔNG xóa gì); ngược lại dùng uid mới."""
    u = _uids_for(session, owner)
    if not u:
        return None
    new, legacy = u
    return legacy if legacy in adopt else new

def _events(sessions, owner, adopt=frozenset()):
    for s in sessions:
        p = parse_session(s)
        if not p:
            continue
        start, end, _ = p
        subj, room = s.get("subjectCode", "Lớp"), s.get("roomNo", "")
        online = fmt.is_online(s)
        uid = _pick_uid(s, owner, adopt)
        yield {
            "iCalUID": uid,
            "summary": subj + (f" @ {room}" if room and not online else (" (Online)" if online else "")),
            "location": "Online" if online else room,
            "description": f"Môn {subj} • Lớp {s.get('groupName','')} • Slot {s.get('slot','')} • "
                           f"GV {s.get('lecturer','')} • Buổi {s.get('sessionNo','')}",
            "start": {"dateTime": start.isoformat(), "timeZone": config.TZID},
            "end":   {"dateTime": end.isoformat(),   "timeZone": config.TZID},
            # fapc=1 giữ nguyên (tương thích ngược) + fapc_owner = mã SV → prune không bao giờ chạm người khác
            "extendedProperties": {"private": {"fapc": "1", "fapc_owner": owner}},
        }

# ---------- DỌN event MỒ CÔI (prune) — CHỈ event CỦA CHÍNH TÔI, KHÔNG đụng lịch cá nhân/người khác ----------
def _current_uids(sessions, owner, adopt=frozenset()):
    """THUẦN: tập iCalUID của lịch HIỆN TẠI (buổi còn hợp lệ) — dùng ĐÚNG quy tắc chọn uid như lúc đẩy,
    nên sự kiện vừa đồng bộ không bao giờ bị coi là mồ côi."""
    return {u for u in (_pick_uid(s, owner, adopt) for s in sessions) if u}

def _is_mine(ev, owner, claim_legacy):
    """THUẦN: event này có phải của TÔI không?
    - có nhãn fapc_owner  → chỉ của tôi khi trùng mã SV (KHÔNG BAO GIỜ đụng profile khác);
    - không có nhãn (lịch CŨ, tạo trước bản này) → chỉ nhận khi `claim_legacy` (profile mặc định)."""
    who = ((ev.get("extendedProperties") or {}).get("private") or {}).get("fapc_owner")
    return (who == owner) if who else bool(claim_legacy)

def _list_fapc_events(svc, cal_id, owner=None, claim_legacy=False):
    """Event fap-cli CỦA TÔI (có phân trang). Lọc server-side theo nhãn private, rồi lọc lại client-side
    theo `fapc_owner` — vì Calendar API không có bộ lọc 'KHÁC giá trị này'.

    owner=None → hành vi cũ (mọi event fapc): chỉ dùng cho code/test cũ, KHÔNG dùng cho prune."""
    def _page(**kw):
        out, page = [], None
        while True:
            resp = svc.events().list(calendarId=cal_id, singleEvents=True, showDeleted=False,
                                     maxResults=2500, pageToken=page, **kw).execute()
            out += resp.get("items", [])
            page = resp.get("nextPageToken")
            if not page:
                return out
    if owner is None:
        return _page(privateExtendedProperty="fapc=1")
    items = _page(privateExtendedProperty=f"fapc_owner={owner}")     # sự kiện đã gắn dấu của tôi
    if claim_legacy:                                                 # + lịch CŨ chưa có dấu (chỉ profile mặc định)
        seen = {ev.get("id") for ev in items}
        items += [ev for ev in _page(privateExtendedProperty="fapc=1")
                  if ev.get("id") not in seen and _is_mine(ev, owner, True)]
    return [ev for ev in items if _is_mine(ev, owner, claim_legacy)]

def _prune_plan(fapc_events, current_uids):
    """THUẦN: event fapc KHÔNG còn trong lịch hiện tại → [(id, iCalUID, summary)] cần XÓA (buổi hủy/dời)."""
    return [(ev.get("id"), ev.get("iCalUID", ""), ev.get("summary", ""))
            for ev in fapc_events if ev.get("iCalUID") and ev.get("iCalUID") not in current_uids]

def _prune(svc, sessions, owner, cal_id, log=print, yes=False, force=False):
    """Xóa event fap-cli MỒ CÔI **của chính mã SV này** trên lịch `cal_id`. Dry-run mặc định (chỉ log);
    >30% thì TỪ CHỐI (phòng lấy lịch lỗi) trừ --force."""
    # Nhận lịch CŨ chưa gắn dấu (fapc=1 không có fapc_owner) để XOÁ chỉ khi: (1) profile MẶC ĐỊNH VÀ
    # (2) lịch KHÔNG cụ thể (thường là 'primary' cá nhân của tôi). Trên lịch CỤ THỂ — vd
    # …@group.calendar.google.com có thể DÙNG CHUNG nhiều người — sự kiện chưa gắn dấu CÓ THỂ của người
    # khác (bản fap-cli cũ của họ), nên prune phải đòi ĐÚNG dấu fapc_owner, tuyệt đối không xoá theo phỏng
    # đoán. (Adopt lúc SYNC vẫn nhận lịch cũ của chính tôi — chỉ giao với UID tôi sắp ghi — nên không trùng.)
    claim_legacy = (not paths.profile()) and not _is_concrete(cal_id)
    fapc = _list_fapc_events(svc, cal_id, owner, claim_legacy)
    adopt = {ev.get("iCalUID", "") for ev in fapc}
    plan = _prune_plan(fapc, _current_uids(sessions, owner, adopt))
    if not plan:
        log(t("✓ Không có sự kiện mồ côi để dọn.", "✓ No orphan events to prune.")); return
    if fapc and len(plan) / len(fapc) > 0.30 and not force:
        log(t(f"⚠️ {len(plan)}/{len(fapc)} sự kiện (>30%) sẽ bị xóa — TỪ CHỐI (lấy lịch có thể lỗi). Ép: thêm --force.",
              f"⚠️ {len(plan)}/{len(fapc)} events (>30%) would be deleted — REFUSED (bad fetch?). Override: --force."))
        return
    log(t(f"{'Đang xóa' if yes else '[DRY-RUN] sẽ xóa'} {len(plan)} sự kiện mồ côi (chỉ event fap-cli của {owner}):",
          f"{'Deleting' if yes else '[DRY-RUN] would delete'} {len(plan)} orphan events (fap-cli, owner {owner} only):"))
    for _id, _uid, summ in plan[:20]:
        log(f"   - {summ}")
    if len(plan) > 20:
        log(f"   … +{len(plan) - 20}")
    if not yes:
        log(t("→ Thêm --yes để xóa thật.", "→ Add --yes to actually delete.")); return
    deleted = 0
    for _id, _uid, summ in plan:
        try:
            svc.events().delete(calendarId=cal_id, eventId=_id).execute(); deleted += 1
        except Exception as e:                       # noqa: BLE001 — 1 event lỗi không dừng cả mẻ
            log("  lỗi xóa · delete error: " + str(e)[:100])
    log(t(f"✓ Đã xóa {deleted} sự kiện mồ côi.", f"✓ Deleted {deleted} orphan events."))

def _adopt_set(svc, owner, cal_id):
    """UID các sự kiện fap-cli CỦA TÔI đang có trên lịch — để đẩy lại là CẬP NHẬT tại chỗ chứ không nhân đôi.

    Bắt buộc phải lấy được: liệt kê hỏng mà vẫn đẩy = lịch cũ (uid không mã SV) bị tạo lại lần 2 dưới
    uid mới ⇒ NHÂN ĐÔI toàn bộ học kỳ. Thà dừng và báo lỗi.

    claim_legacy=True KỂ CẢ khi đang chạy profile: nếu chỉ profile mặc định mới nhận lịch cũ thì một
    người dùng sẵn có vừa đặt tên profile cho mình sẽ KHÔNG nhận lại lịch cũ của chính mình ⇒ nhân đôi
    cả kỳ. An toàn vì việc "nhận nuôi" chỉ ÁP DỤNG cho đúng các uid mà lượt đẩy này sắp ghi (giao với
    lịch học của chính tôi) — KHÁC hẳn đường PRUNE (xoá) bên dưới, ở đó vẫn giữ claim_legacy nghiêm ngặt:
    không bao giờ XOÁ một sự kiện chưa gắn dấu mà mình không chứng minh được là của mình."""
    try:
        return {ev.get("iCalUID", "") for ev in
                _list_fapc_events(svc, cal_id, owner, claim_legacy=True)}
    except Exception as e:                                # noqa: BLE001 — mọi lỗi API đều dẫn tới cùng 1 kết luận
        raise SystemExit(t(
            f"Không đọc được sự kiện sẵn có trên Calendar ({str(e)[:120]}). DỪNG để tránh nhân đôi lịch.",
            f"Could not read existing calendar events ({str(e)[:120]}). STOPPING to avoid duplicating the calendar."))


# ───────────────────────── LÕI SYNC/PRUNE (log=callback: dùng chung CLI + chat) ─────────────────────────
def _sync(label="", log=print, prune=False, yes=False, force=False):
    """Đẩy lịch học lên đích `label`. `log` nhận từng dòng (print cho CLI, list.append cho chat)."""
    _check_no_dupe(label)                                 # chặn xóa chéo TRƯỚC khi chạm mạng
    cal_id = _calendar_id(label)
    token, campus, roll = creds()
    owner = _owner(roll)
    sem = current_semester(token, campus, roll)
    sessions = fetch_sessions(token, campus, roll, sem)
    where = (f" [{label}]" if label else "") + paths.label()
    log(t(f"Lấy {len(sessions)} buổi (kỳ {sem}). Đang đẩy lên Calendar '{cal_id}' (chủ sở hữu: {owner}){where}...",
          f"Fetched {len(sessions)} sessions ({sem}). Pushing to calendar '{cal_id}' (owner: {owner}){where}..."))
    svc = _service(label)
    adopt = _adopt_set(svc, owner, cal_id)               # "nhận nuôi" lịch đã có: giữ nguyên uid cũ, chỉ gắn thêm dấu chủ sở hữu
    ok = fail = 0
    for ev in _events(sessions, owner, adopt):
        try:
            svc.events().import_(calendarId=cal_id, body=ev).execute()  # upsert theo iCalUID
            ok += 1
        except Exception as e:                           # noqa: BLE001
            fail += 1
            if fail <= 3: log("  lỗi 1 sự kiện: " + str(e)[:120])
    log(t(f"✓ Đồng bộ {ok} sự kiện (lỗi {fail}). Chạy lại = cập nhật, không trùng.",
          f"✓ Synced {ok} events (failed {fail}). Re-run = update, no duplicates."))
    if prune:                                            # dọn event buổi-đã-hủy/dời (chỉ event fap-cli của tôi)
        _prune(svc, sessions, owner, cal_id, log=log, yes=yes, force=force)


def _prune_only(label="", log=print, yes=False, force=False):
    """Dọn RIÊNG (không đẩy lại) trên đích `label`."""
    _check_no_dupe(label)
    cal_id = _calendar_id(label)
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    _prune(_service(label), fetch_sessions(token, campus, roll, sem), _owner(roll), cal_id,
           log=log, yes=yes, force=force)


def _collect(fn, *a, **kw):
    """Chạy `fn(log=lines.append, …)` và trả CHUỖI (cho chat). Nuốt SystemExit (token hết hạn / chưa
    xác thực / trùng lịch / thiếu lib) thành text sạch thay vì phun traceback vào chat."""
    lines = []
    try:
        fn(*a, log=lines.append, **kw)
    except SystemExit as e:
        lines.append(str(e))
    except Exception as e:                                # noqa: BLE001 — chat không được chết vì 1 lệnh
        lines.append(t(f"Lỗi calendar: {type(e).__name__}: {e}", f"Calendar error: {type(e).__name__}: {e}"))
    return "\n".join(str(l) for l in lines) or t("(không có gì để hiển thị)", "(nothing to show)")


def sync_text(label="", prune=False, yes=False, force=False):
    """Bản trả-CHUỖI của sync — cho bot Telegram/Discord."""
    return _collect(_sync, label, prune=prune, yes=yes, force=force)


def prune_text(label="", yes=False, force=False):
    """Bản trả-CHUỖI của prune — cho bot Telegram/Discord."""
    return _collect(_prune_only, label, yes=yes, force=force)


# ───────────────────────── CLI (in ra stdout) ─────────────────────────
def cmd_auth(label=""):
    """Xác thực Google (loopback-paste) cho một đích, ngay trên máy chủ không màn hình."""
    try:
        url, label = gcal_auth_url(label)
    except ValueError as e:                                # nhãn không hợp lệ -> CHỮ sạch, không traceback
        print("⛔ " + str(e)); return
    print(t("🔐 Mở URL này, đăng nhập Google, rồi DÁN URL trên thanh địa chỉ vào đây",
            "🔐 Open this URL, sign in to Google, then PASTE the address-bar URL back here") +
          t(" (trình duyệt sẽ báo 'không kết nối được 127.0.0.1' — ĐÚNG rồi):",
            " (the browser will say 'can't connect to 127.0.0.1' — that's EXPECTED):"))
    print("\n" + url + "\n")
    try:
        pasted = input(t("Dán URL redirect: ", "Paste redirect URL: ")).strip()
    except (EOFError, KeyboardInterrupt):
        print(t("\nĐã hủy.", "\nCancelled.")); return
    print(gcal_auth_finish(pasted, label))


def cmd_sync(prune=False, yes=False, force=False, label=""):
    try:
        _sync(label, log=print, prune=prune, yes=yes, force=force)
    except ValueError as e:                                # nhãn không hợp lệ (norm_label) -> CHỮ sạch
        print("⛔ " + str(e))


def cmd_prune(yes=False, force=False, label=""):
    try:
        _prune_only(label, log=print, yes=yes, force=force)
    except ValueError as e:
        print("⛔ " + str(e))


def cmd_add(label, calendar_id):
    print(add_destination(label, calendar_id))


def cmd_remove(label):
    print(remove_destination(label))


def cmd_list():
    print(destinations_text())


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "sync"
    rest = [a for a in args[1:] if not a.startswith("--")]
    label = rest[0] if rest else ""
    flags = {"yes": "--yes" in args, "force": "--force" in args}
    if cmd == "auth":     cmd_auth(label)
    elif cmd == "add":    cmd_add(label, rest[1] if len(rest) > 1 else "")
    elif cmd == "remove": cmd_remove(label)
    elif cmd == "list":   cmd_list()
    elif cmd == "prune":  cmd_prune(label=label, **flags)
    else:                 cmd_sync(prune="--prune" in args, label=label, **flags)

if __name__ == "__main__":
    main()
