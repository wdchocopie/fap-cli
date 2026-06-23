#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fmt.py — định dạng tin nhắn dùng chung (chat + console). THUẦN định dạng, không gọi mạng/IO.

Gom các mảnh hay lặp: tên thứ trong tuần, nhãn phòng/online, đường kẻ, tiêu đề, nhãn trạng thái.
Dùng emoji + xuống dòng thay vì căn cột (font chat KHÔNG đều) để hiển thị đẹp trên Telegram/Discord/console.
"""
import datetime, html
from .config import FAP_LANG

def unescape(s):
    """Giải mã HTML entity (vd '&#224;' -> 'à', '&quot;' -> '\"') — text từ FAP (đơn từ/tin tức/thông báo)
    hay chứa entity, nếu không decode sẽ hiện mojibake."""
    return html.unescape(str(s if s is not None else "")).strip()

def _vi():
    return not str(FAP_LANG).lower().startswith("en")

WD_VI = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RULE = "━━━━━━━━━━━━━━━━"     # đường kẻ ngăn tiêu đề

def weekday(d):
    return (WD_VI if _vi() else WD_EN)[d.weekday()]

def is_online(s):
    return str(s.get("isOnline")).strip().lower() in ("true", "1", "yes", "online")

def room(s):
    """Nhãn phòng có icon: '💻 Online' hoặc '📍 <phòng>'."""
    return "💻 Online" if is_online(s) else ("📍 " + (s.get("roomNo") or "?"))

def header(emoji, title, sub=None):
    """Dòng tiêu đề + đường kẻ. sub = chú thích nhỏ bên phải (vd số buổi)."""
    return f"{emoji} {title}" + (f"  ·  {sub}" if sub else "") + "\n" + RULE

def fmt_date(d):
    """'2026-06-22T00:00:00' -> '22/06/2026'."""
    try:
        return datetime.datetime.fromisoformat(str(d).split("T")[0]).strftime("%d/%m/%Y")
    except ValueError:
        return str(d)

_STATUS = {"present": "Có mặt ✅", "absent": "VẮNG ❌", "late": "Đi muộn ⏰",
           "future": "Chưa tới", "notyet": "Chưa tới", "not yet": "Chưa tới"}

def status_label(s):
    """Nhãn trạng thái điểm danh có icon (vi) hoặc giữ nguyên (en)."""
    return _STATUS.get(str(s).strip().lower(), str(s)) if _vi() else str(s)

# ---------- tiện ích số/điểm dùng chung ----------
def safe_float(x, default=0.0):
    """float an toàn: '' / None / không-parse-được -> default."""
    try: return float(x or 0)
    except (TypeError, ValueError): return default

def has_mark(r):
    """Môn ĐÃ có điểm tổng kết (averageMark > 0). Tránh magic-string ('0.0','0',...)."""
    return safe_float(r.get("averageMark")) > 0

def gpa_val(g):
    """Token giá trị GPA tạm tính: số, hoặc 'chưa có'/'n/a' khi None. Dùng chung 4 chỗ (đỡ lặp)."""
    from .i18n import t                       # import trong hàm: fmt KHÔNG import i18n ở top (tránh vòng)
    return g if g is not None else t("chưa có", "n/a")

def table(rows):
    """Bảng generic (chuỗi) theo ĐÚNG field server trả — KHÔNG bịa cột. Dùng chung cho
    transcript / fees / news / điểm-thành-phần. rows không phải dict -> liệt kê thô."""
    rows = [r for r in rows if r is not None]
    cols = []
    for r in rows:
        if isinstance(r, dict):
            for k in r:
                if k not in cols:
                    cols.append(k)
    if not cols:                          # không có dict nào -> in thô từng dòng
        return "\n".join(f"  {r}" for r in rows)
    drows = [r for r in rows if isinstance(r, dict)]
    w = {c: max(len(str(c)), max((len(str(r.get(c, ""))) for r in drows), default=0)) for c in cols}
    out = ["  " + "  ".join(str(c).ljust(w[c]) for c in cols)]
    out += ["  " + "  ".join(str(r.get(c, "")).ljust(w[c]) for c in cols) for r in drows]
    return "\n".join(out)
