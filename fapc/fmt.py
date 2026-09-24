#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fmt.py — định dạng tin nhắn dùng chung (chat + console). THUẦN định dạng, không gọi mạng/IO.

Gom các mảnh hay lặp: tên thứ trong tuần, nhãn phòng/online, đường kẻ, tiêu đề, nhãn trạng thái.
Dùng emoji + xuống dòng thay vì căn cột (font chat KHÔNG đều) để hiển thị đẹp trên Telegram/Discord/console.
"""
import datetime, html, re
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

# Link vào lớp ONLINE. Key GỐC trong GetActivityStudent(+ByWeek) là `meetURL` — bundle app đọc đúng key
# này rồi đổi tên nội bộ thành `meeturl`, nên nhận cả hai.
# ⚠️ Dù tên là "URL", dữ liệu THẬT là MÃ PHÒNG Google Meet TRẦN dạng `abc-defg-hij` (đã đo trên dump
# thật: 28/28 giá trị khớp mẫu 3-4-3, KHÔNG giá trị nào bắt đầu bằng http). Nếu chỉ nhận http(s) thì
# tính năng này im lặng không hiện link nào. Field có mặt ở mọi buổi nhưng "" ở phần lớn buổi.
_MEET_KEYS = ("meetURL", "meeturl")
_MEET_CODE = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$")   # mã phòng Google Meet (chữ thường, 3-4-3)
# URL đầy đủ: MỘT token https, host thuộc nhà cung cấp phòng họp quen biết, bộ ký tự an toàn — KHÔNG có
# khoảng trắng / [ ] ( ) < > @ * | `. Dòng link đứng NGAY SAU nhãn "Vào lớp" (chỗ người dùng quen bấm):
# không được để chuỗi từ server chèn link mạo danh '[Vào lớp](https://…)' hay '@everyone' (Discord render
# markdown + mention trong content). Không khớp -> KHÔNG hiện link (thà thiếu còn hơn sai).
_MEET_URL = re.compile(r"^https://([A-Za-z0-9.-]+)(/[A-Za-z0-9\-._~/?#=&%+:]*)?$")
_MEET_HOSTS = ("meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com")

def _meet_host_ok(host):
    """Host thuộc nhà cung cấp phòng họp (kể cả subdomain như us02web.zoom.us; KHÔNG khớp 'evilzoom.us')."""
    return any(host == h or host.endswith("." + h) for h in _MEET_HOSTS)

def meet_url(s):
    """THUẦN: link vào lớp online của 1 buổi, '' nếu không có.

    Chỉ trả khi buổi ONLINE (cờ isOnline qua is_online — KHÔNG suy online từ việc có mã: mã Meet gắn
    cả vào buổi học TẠI PHÒNG). Nhận:
      • mã Meet trần 'abc-defg-hij'     -> https://meet.google.com/abc-defg-hij   (dạng FAP đang trả, 28/28)
      • 'meet.google.com/…' thiếu scheme -> thêm https:// rồi kiểm như URL
      • URL https đầy đủ trên Meet/Zoom/Teams, đúng MỘT token, bộ ký tự an toàn (xem _MEET_URL)
    Mọi thứ khác ('N/A', rác, http://, host lạ, có khoảng trắng/markdown) -> ''. Mã chỉ được ghép vào URL
    khi khớp ĐÚNG mẫu 3-4-3; URL không bao giờ bị "cắt bớt cho vừa" — không hợp lệ là bỏ hẳn."""
    if not is_online(s):
        return ""
    for k in _MEET_KEYS:
        v = str(s.get(k) or "").strip()
        if not v:
            continue
        low = v.lower()
        if _MEET_CODE.match(low):
            return "https://meet.google.com/" + low
        if low.startswith("meet.google.com/"):
            v = "https://" + v
        elif low.startswith("https://"):
            v = "https://" + v[8:]                          # chuẩn hoá chữ hoa trong scheme
        m = _MEET_URL.match(v)
        if m and _meet_host_ok(m.group(1).lower()):
            return v
    return ""

def meet_line(s, indent="", label=""):
    """THUẦN: dòng '🔗 <nhãn><link>' ('' nếu buổi không có link online).

    Link đứng RIÊNG một dòng, ở CUỐI dòng: Telegram/Discord gửi plain text (không parse_mode) nên tự
    nhận diện URL thành link bấm được, không dính chữ phía sau. `label` do caller dịch sẵn (fmt không
    phụ thuộc i18n), vd t('Vào lớp: ', 'Join: ')."""
    u = meet_url(s)
    return f"{indent}🔗 {label}{u}" if u else ""

def with_meet(line, s, indent="", label=""):
    """THUẦN: `line` + (xuống dòng + dòng link online nếu có). Vẫn là MỘT chuỗi cho MỘT buổi — caller
    thường đếm 'số buổi' bằng len(danh sách dòng) (vd dashboard.status), tách link ra phần tử riêng
    sẽ làm sai con số đó."""
    m = meet_line(s, indent, label)
    return line + "\n" + m if m else line

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

def chunks(text, limit):
    """THUẦN: cắt `text` thành các mẩu ≤ `limit` ký tự để gửi NHIỀU tin thay vì cắt cụt.

    Ưu tiên cắt ở RANH GIỚI DÒNG (chat đọc mới xuôi); dòng đơn dài hơn `limit` mới cắt cứng.
    Luôn trả ≥1 phần tử (text rỗng -> ['']), không mẩu nào vượt `limit` -> gọi thẳng vào API chat
    được mà không sợ mất chữ. `limit` <= 0 -> trả nguyên văn (không cắt)."""
    text = "" if text is None else str(text)
    if limit is None or limit <= 0 or len(text) <= limit:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:                  # 1 dòng dài quá khổ -> buộc phải cắt cứng
            if cur:
                out.append(cur); cur = ""
            out.append(line[:limit]); line = line[limit:]
        add = line if not cur else cur + "\n" + line
        if len(add) <= limit:
            cur = add
        else:
            out.append(cur); cur = line
    if cur or not out:
        out.append(cur)
    return out


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
