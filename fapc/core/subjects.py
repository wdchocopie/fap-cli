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
from .api import call, as_list, checksum_login
from .. import fmt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(_ROOT, "output", "subjects_catalog.json")

_INDEX = None        # {code: {"en","vi","credits","replacedBy"}} — memo trong tiến trình (None = chưa nạp)

def fetch_catalog(token, campus, roll):
    """GetSubjets: toàn bộ danh mục môn của campus. Dùng checksum_login (KHÁC cs12 mặc định)."""
    _, data = call("GetSubjets", [("campusCode", campus), ("Authen", token)], roll, campus,
                   checksum_value=checksum_login(campus))
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
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
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
