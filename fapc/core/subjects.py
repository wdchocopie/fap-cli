#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subjects.py — Danh mục môn (GetSubjets) → tra TÊN + TÍN CHỈ theo mã môn.

API trả mã trơ ('HOD402') ở khắp nơi; module này join với danh mục để hiện
'HOD402 — Human-Computer Interaction' và cấp số tín chỉ cho GPA theo TRỌNG SỐ.

Danh mục tải 1 lần (lệnh `fap subjects`) rồi cache `output/subjects_catalog.json` (toàn campus) → các
lượt sau đọc cache, KHÔNG gọi mạng. `load()` chỉ ĐỌC cache (không tự fetch ở lệnh nóng → không thêm độ
trễ). KHÔNG bao giờ raise: thiếu danh mục → trả mã trơ / 0 tín chỉ (mọi nơi degrade êm).
"""
import os, json
from .api import call_login_retry, as_list
from . import paths
from .. import fmt

# Danh mục để RIÊNG từng profile: dữ liệu nhỏ, và mỗi profile có thể khác campus (GetSubjets theo campus).
CACHE = paths.out("subjects_catalog.json")   # output/… hoặc output/profiles/<tên>/… (xem core/paths.py)

_INDEX = None        # {code: {"en","vi","credits","replacedBy"}} — memo trong tiến trình (None = chưa nạp)

def fetch_catalog(token, campus, roll):
    """GetSubjets: toàn bộ danh mục môn của campus. Ký bằng checksum_login (KHÁC cs12 mặc định) → override
    nên call() không tự retry; dùng call_login_retry để thử ±1h (khỏi rỗng danh mục lúc lệch giờ đầu giờ)."""
    _, data = call_login_retry("GetSubjets", [("campusCode", campus), ("Authen", token)], roll, campus)
    return as_list(data)

def index_of(rows):
    """THUẦN: list GetSubjets → {subjectCode: {en, vi, credits, replacedBy}}."""
    idx = {}
    for r in rows:
        code = str(r.get("subjectCode") or "").strip()
        if code:
            idx[code] = {
                "en": str(r.get("subjectName") or "").strip(),
                "vi": str(r.get("subjectV") or "").strip(),
                "credits": fmt.safe_float(r.get("credits")),
                "replacedBy": str(r.get("replacedBy") or "").strip().strip(","),
            }
    return idx

def _read_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None

def _write_cache(idx):
    try:
        paths.ensure_dir(CACHE)                    # thư mục profile có thể chưa tồn tại
        # tmp RIÊNG theo tiến trình: watch-attendance + watch-grades cùng profile khởi động trong cùng
        # giây và cả hai gọi subjects.load()/refresh() -> tên tmp dùng chung sẽ ghi đè nhau giữa chừng.
        tmp = f"{CACHE}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CACHE)
    except OSError:
        pass

def load():
    """Trả index từ cache (memo trong tiến trình). KHÔNG fetch — dùng `refresh()` để tải mới."""
    global _INDEX
    if _INDEX is None:
        _INDEX = _read_cache() or {}
    return _INDEX

def refresh(token, campus, roll):
    """Tải lại danh mục từ GetSubjets, lưu cache, cập nhật memo. Trả index (rỗng nếu hỏng)."""
    global _INDEX
    try:
        rows = fetch_catalog(token, campus, roll)
    except Exception:                              # noqa: BLE001 — danh mục không sống còn
        rows = []
    if rows:
        _INDEX = index_of(rows)
        _write_cache(_INDEX)
    return _INDEX or {}

def set_index(idx):
    """Inject thẳng index (cho test/offline) — bỏ qua mạng & cache."""
    global _INDEX
    _INDEX = dict(idx or {})

def name(code, idx=None):
    """Tên môn theo FAP_LANG (VI ưu tiên khi lang=vi). '' nếu không có danh mục."""
    info = (idx if idx is not None else load()).get(code)
    if not info:
        return ""
    return (info.get("vi") if fmt._vi() else info.get("en")) or info.get("en") or info.get("vi") or ""

def label(code, idx=None):
    """'HOD402 — Human-Computer Interaction' nếu tra được, ngược lại chỉ 'HOD402'."""
    nm = name(code, idx)
    code = code or ""
    return f"{code} — {nm}" if nm else code

def credit_of(code, idx=None):
    """Số tín chỉ của môn (0.0 nếu không tra được) — cho GPA theo trọng số."""
    info = (idx if idx is not None else load()).get(code)
    return float(info.get("credits") or 0.0) if info else 0.0

def resolve(query, codes, idx=None):
    """THUẦN (không mạng, không đọc đĩa): 'iap' + danh sách mã môn → (mã CHUẨN | None, ứng viên).

    Ưu tiên giảm dần: mã khớp ĐÚNG > mã BẮT ĐẦU BẰNG > mã CHỨA > TÊN môn CHỨA. Không phân biệt hoa/thường.
    Trả về mã **CHUẨN** (đúng hoa/thường như server gửi) vì chính mã này được gửi NGƯỢC lên server
    (`grades._mark_params` → `SubjectCode`): mã thật có hoa-thường lẫn lộn ('FRS401c') nên KHÔNG được
    trả lại nguyên chuỗi người dùng gõ.

    - Đúng 1 ứng viên ở một tầng ưu tiên → `(mã, [mã])`.
    - Nhiều ứng viên ở tầng đó → `(None, ứng_viên)` để caller liệt kê cho người dùng chọn lại.
    - Không khớp gì (hoặc `query` rỗng) → `(None, tất_cả_mã)` để caller liệt kê môn trong kỳ.

    `idx`: index danh mục môn (`{mã: {"en","vi",...}}`) cho tầng khớp TÊN. `None` → dùng memo đã nạp
    sẵn trong tiến trình; KHÔNG tự `load()` (đọc file) để hàm này thuần & test offline được.
    """
    seen, uniq = set(), []
    for c in (codes or []):                     # khử trùng lặp, GIỮ thứ tự (caller hợp nhất 2 nguồn mã)
        c = str(c).strip()
        if c and c.lower() not in seen:
            seen.add(c.lower()); uniq.append(c)
    q = str(query or "").strip().lower()
    if not q or not uniq:
        return None, uniq
    idx = idx if idx is not None else (_INDEX or {})

    def _names(code):
        info = idx.get(code) or {}
        return [n for n in (str(info.get("vi") or ""), str(info.get("en") or "")) if n]

    for cands in ([c for c in uniq if c.lower() == q],
                  [c for c in uniq if c.lower().startswith(q)],
                  [c for c in uniq if q in c.lower()],
                  [c for c in uniq if any(q in n.lower() for n in _names(c))]):
        if len(cands) == 1:
            return cands[0], [cands[0]]
        if cands:
            return None, cands                  # mơ hồ — caller liệt kê ứng viên
    return None, uniq                           # không khớp — caller liệt kê cả kỳ

# ---------- lệnh `fap subjects` ----------
def report(refresh_now=True):
    from .api import creds
    from ..i18n import t
    token, campus, roll = creds()
    idx = refresh(token, campus, roll) if refresh_now else load()
    if not idx:
        print(t("Không tải được danh mục môn (token hết hạn? thử `fap refresh`).",
                "Couldn't load the subject catalog (token expired? try `fap refresh`).")); return
    print(t(f"📚 Danh mục môn: {len(idx)} môn (đã cache → tên & tín chỉ hiện ở mọi nơi).",
            f"📚 Subject catalog: {len(idx)} subjects (cached → names & credits show everywhere)."))
    for code in list(idx)[:8]:
        info = idx[code]
        print(f"  {code:8} {info.get('credits') or '?':>2}tc  {info.get('vi') or info.get('en')}")
    if len(idx) > 8:
        print(t(f"  … và {len(idx) - 8} môn khác.", f"  … and {len(idx) - 8} more."))
