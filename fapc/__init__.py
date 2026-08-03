"""fapc — fap-cli. Đăng nhập FAP qua OAuth + kéo dữ liệu + .ics + Google Calendar + notify."""
__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Nạp .env NGAY khi import package (trước mọi submodule) để api.py thấy FAP_SEMESTER.
#
# ĐÂY LÀ LOADER .env DUY NHẤT của dự án. `fapc/config.py` gọi lại chính hàm này
# (idempotent — lần gọi thứ hai không làm gì) thay vì tự đọc .env lần nữa.
# Trước đây có HAI loader độc lập: loader thứ hai bơm lại TELEGRAM_CHAT của chủ máy
# vào profile của bạn bè ⇒ điểm của bạn bè bắn vào chat của chủ máy. Xem docs/18-roadmap.md §4.
#
# Hàm này phải KHÔNG phụ thuộc gì (chỉ `os` + đọc file thuần): nó chạy trước cả
# fapc.config lẫn fapc.core.paths, nên import bất cứ submodule nào ở đây = vòng import.
# ---------------------------------------------------------------------------
import os as _os
import re as _re
import sys as _sys

# Nhiều tài khoản trên CÙNG 1 máy: mỗi profile một file env riêng ở gốc repo.
#     FAP_PROFILE=alice  ->  <gốc repo>/.env.alice   (đọc TRƯỚC .env gốc nên nó THẮNG)
# File này phải được gitignore (nó chứa token/chat id của người khác).
_PROFILE_ENV_FMT = ".env.{}"

# Tên profile hợp lệ — GIỮ GIỐNG `fapc/core/paths.py:_SAFE` (không import được vì vòng import):
# chỉ chữ/số/._- , chặn '..' và dấu phân cách đường dẫn. Tên sai ⇒ coi như KHÔNG dùng profile,
# đúng y hệt cách paths.profile() xử lý, để env và đường dẫn không bao giờ lệch nhau.
_SAFE_PROFILE = _re.compile(r"^[A-Za-z0-9._-]+$")

# Khóa mang DANH TÍNH / KÊNH GỬI. Khi một profile đang chạy, các khóa này TUYỆT ĐỐI
# không được thừa kế từ .env gốc: profile nào không tự khai thì kênh đó TẮT HẲN
# (an toàn) — thay vì im lặng rơi về chat/lịch/quyền của chủ máy (rò dữ liệu).
_IDENTITY_KEYS = frozenset({
    "FAP_PROFILE",              # bản thân bộ chọn profile — không bao giờ thừa kế
    "TELEGRAM_TOKEN",           # bot nào gửi
    "TELEGRAM_CHAT",            # gửi VÀO chat nào  ← chính là chỗ rò
    "DISCORD_WEBHOOK_URL",      # webhook của server/kênh nào
    "DISCORD_BOT_TOKEN",        # bot Discord nào
    "DISCORD_ALLOWED_USER_ID",  # bot chỉ trả lời user nào
    "DISCORD_ALLOW_ANYONE",     # nới quyền của bot — thừa kế = mở toang bot của người khác
    "GCAL_CALENDAR_ID",         # ghi vào lịch Google nào
})

# Quyền tác động lên CHECKOUT DÙNG CHUNG (git pull + os.execv restart). Khi có profile, các khóa này
# bị bỏ qua ở CẢ .env.<profile> LẪN .env gốc: khách không được TỰ CẤP quyền cho mình (đặt vào
# .env.alice), cũng không được THỪA KẾ quyền của chủ máy. Chỉ tiến trình KHÔNG profile mới dùng được.
_OWNER_ONLY_KEYS = frozenset({
    "FAP_ALLOW_UPDATE",         # bật lệnh bot /update
    "FAP_AUTOUPDATE_MIN",       # tự pull+restart nền — cùng quyền lực, phải cùng mức chặn
})

_ENV_LOADED = False


def _env_pairs(path):
    """Đọc file dạng KEY=VALUE -> [(key, value)]. Không tồn tại / đọc lỗi -> []."""
    try:
        if not _os.path.exists(path):
            return []
        pairs = []
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                pairs.append((k.strip(), v.strip().strip('"').strip("'")))   # bỏ nháy bao quanh
        return pairs
    except OSError:
        return []


def _apply(pairs, skip=frozenset()):
    """setdefault từng cặp vào os.environ (đặt trước = THẮNG), bỏ qua khóa trong `skip`."""
    for k, v in pairs:
        if k and k not in skip:
            _os.environ.setdefault(k, v)


def _profile_name(root):
    """Tên profile đang chạy ('' nếu không có). Ưu tiên biến môi trường THẬT (systemd/shell);
    nếu chưa có thì mới ngó FAP_PROFILE trong .env gốc — nếu không ngó, một người đặt
    FAP_PROFILE trong .env sẽ có đường dẫn theo profile (paths.py đọc sau) nhưng lại nạp
    TOÀN BỘ .env gốc ⇒ vẫn rò. Tên không hợp lệ -> '' (giống paths.profile(), không raise)."""
    name = (_os.environ.get("FAP_PROFILE") or "").strip()
    if not name:
        for k, v in _env_pairs(_os.path.join(root, ".env")):
            if k == "FAP_PROFILE":
                name = v.strip()
    if not name:
        return ""
    # '.' và '..' KHỚP regex nhưng là tên thư mục đặc biệt — paths.profile() loại chúng, nên ở đây
    # phải loại y hệt. Nếu lệch: tầng env chạy CHẾ ĐỘ PROFILE còn tầng đường dẫn chạy CHẾ ĐỘ CHỦ MÁY
    # ⇒ nạp .env.. của khách nhưng ghi state vào output/ của chủ máy.
    if name in (".", "..") or not _SAFE_PROFILE.match(name):
        # Không raise (một biến gõ nhầm không được làm chết mọi lệnh) nhưng phải KÊU TO:
        # rơi về chế độ 1 tài khoản nghĩa là dùng .env + output/ của CHỦ MÁY.
        _sys.stderr.write(
            "⚠️  FAP_PROFILE=%r không hợp lệ (chỉ cho phép chữ/số/._-) — BỎ QUA, chạy như KHÔNG có "
            "profile: dùng .env và output/ của chủ máy.\n"
            "⚠️  FAP_PROFILE=%r is invalid (letters/digits/._- only) — IGNORED, running with NO "
            "profile: the owner's .env and output/ are used.\n" % (name, name))
        return ""
    return name


def load_env():
    """Nạp .env vào os.environ. IDEMPOTENT: gọi bao nhiêu lần cũng chỉ chạy thật 1 lần.

    Không profile:  chỉ <gốc repo>/.env  (y HỆT hành vi cũ).
    Có profile:     <gốc repo>/.env.<profile> TRƯỚC (setdefault = đặt trước thắng),
                    rồi .env gốc CHỈ cho các khóa không mang danh tính (_IDENTITY_KEYS bị chặn).
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    prof = _profile_name(root)
    if not prof:
        _apply(_env_pairs(_os.path.join(root, ".env")))
        return

    # Chốt lại FAP_PROFILE vào môi trường để paths.py (đọc sau) thấy ĐÚNG cái tên này.
    _os.environ.setdefault("FAP_PROFILE", prof)
    penv = _os.path.join(root, _PROFILE_ENV_FMT.format(prof))
    if not _os.path.exists(penv):
        # .env gốc bị lọc hết khóa danh tính ⇒ KHÔNG có file này thì mọi kênh gửi TẮT ÂM THẦM
        # (đúng về mặt an toàn, nhưng người dùng phải biết vì sao bot im lặng).
        _sys.stderr.write(
            "⚠️  FAP_PROFILE=%s nhưng KHÔNG thấy %s — mọi kênh gửi (Telegram/Discord/Calendar) sẽ TẮT.\n"
            "    Tạo file đó rồi khai khóa riêng của profile này (xem docs/19-multi-profile.md).\n"
            "⚠️  FAP_PROFILE=%s but %s is MISSING — every delivery channel will be OFF.\n"
            % (prof, _PROFILE_ENV_FMT.format(prof), prof, _PROFILE_ENV_FMT.format(prof)))
    # Khóa quyền-chủ-máy bị chặn ở CẢ HAI file: khách không tự cấp, cũng không thừa kế.
    _apply(_env_pairs(penv), skip=_OWNER_ONLY_KEYS)
    _apply(_env_pairs(_os.path.join(root, ".env")), skip=_IDENTITY_KEYS | _OWNER_ONLY_KEYS)


_load_env = load_env   # tên cũ, giữ lại cho tương thích

load_env()
