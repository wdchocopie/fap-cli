#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gradewatch.py — Báo khi có ĐIỂM MỚI (thành phần hoặc tổng kết) — near real-time.

    fap watch-grades              # 1 lượt: dò thay đổi -> báo lên kênh -> thoát (cho cron)
    fap watch-grades loop [phút]  # chạy nền, dò mỗi <phút> (mặc định 30), 06:00–22:00 giờ VN

Giống watch-attendance: FAP không đẩy cho mình -> phải POLL. So GetStudentMark (+ GetMarkByCourse
cho điểm thành phần) với lần trước; chỉ báo phần MỚI/ĐỔI. Mỗi điểm chỉ báo ĐÚNG 1 LẦN
(nhớ trong output/grade_state.json). Im lặng khi không có gì mới.
"""
import os, sys, json, time, re
from ..core.api import creds, current_semester, _vn_now
from ..core.grades import fetch_marks, fetch_components
from ..core import paths
from .notify import push
from .attendwatch import _refresh_token          # dùng chung: tự làm mới token cho service chạy nền
from .selfupdate import maybe_autoupdate, autoupdate_min
from ..i18n import t
from .. import fmt

STATE = paths.out("grade_state.json")            # theo profile (FAP_PROFILE); chưa đặt ⇒ output/grade_state.json như cũ

# Lệch giờ refresh token lúc khởi động — bảng phân dải dùng chung ở fapc/app/_stagger.py.
from ._stagger import startup_delay

# Field "tên" và "giá trị" của 1 đầu điểm có thể khác nhau theo campus -> dò generic, không bịa.
_VAL_KEYS = {"value", "mark", "grade", "score", "point", "averagemark", "result", "valuestr"}
_NAME_KEYS = ("component", "componentName", "name", "item", "title", "gradeComponentName", "categoryName", "type")

def _comp_key(c):
    for k in _NAME_KEYS:
        if c.get(k):
            return str(c[k])
    return "|".join(f"{k}={c[k]}" for k in sorted(c) if str(k).lower() not in _VAL_KEYS)

def _comp_val(c):
    for k in c:
        if str(k).lower() in _VAL_KEYS and c[k] not in (None, ""):
            return str(c[k])
    return ""        # đầu điểm CHƯA có giá trị

def _snapshot(avg, comps):
    return {"avg": str(avg if avg is not None else ""),
            "comps": {_comp_key(c): _comp_val(c) for c in comps}}

def compute(marks, detail_fn, state):
    """Lõi THUẦN (không mạng/IO) — test offline được.
    marks: list GetStudentMark; detail_fn(subj, cid) -> list đầu điểm hoặc None nếu lấy HỎNG; state cũ.
    Trả (events[str], new_state, first_run)."""
    first_run = not state
    new_state, events = {}, []
    for r in marks:
        subj, cid = r.get("subjectCode", ""), r.get("courseID")
        prev = state.get(subj, {})
        comps = detail_fn(subj, cid)
        if comps is None:                         # chi tiết lấy HỎNG -> GIỮ mốc cũ, dò lại lượt sau
            if subj in state:
                new_state[subj] = prev
            continue
        snap = _snapshot(r.get("averageMark"), comps)
        if not first_run and prev:
            old = prev.get("comps", {})
            for k, v in snap["comps"].items():    # đầu điểm mới xuất hiện hoặc đổi giá trị
                ov = old.get(k, "")
                # cả 2 là số dương -> so theo SỐ ('8.5' vs '8.50' / '9' vs '9.0' KHÔNG báo nhầm); còn lại so chuỗi
                if v.strip() and ov.strip() and fmt.safe_float(v) > 0 and fmt.safe_float(ov) > 0:
                    differs = fmt.safe_float(v) != fmt.safe_float(ov)
                else:
                    differs = v != ov
                if v and differs:
                    events.append({"subj": subj, "item": k, "value": v})
            oa, na = prev.get("avg", ""), snap["avg"]   # so theo SỐ -> '8.5' vs '8.50' không báo nhầm
            if fmt.safe_float(na) > 0 and fmt.safe_float(na) != fmt.safe_float(oa):
                events.append({"subj": subj, "item": None, "value": na})   # item=None => điểm tổng kết môn
        new_state[subj] = snap
    return events, new_state, first_run

def _natkey(s):
    """Khoá sort TỰ NHIÊN: 'LAB 2' đứng trước 'LAB 10' (tách cụm số ra so theo GIÁ TRỊ, không theo chuỗi)."""
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", str(s or ""))]

# ── Gộp thông báo điểm mới ────────────────────────────────────────────────────────────────────
# Tất cả helper dưới đây THUẦN (không mạng/IO) -> test offline được.
# Nhóm CỐ ĐỊNH theo thứ tự này; phân loại bằng TÊN đầu điểm (FAP không trả loại chuẩn hoá).
_BUCKETS = (("lab", "🔬"), ("prog", "📝"), ("other", "📎"), ("final", "🏁"))

_RE_LAB   = re.compile(r"\blabs?\b", re.I)
_RE_PROG  = re.compile(r"progress|mid[- ]?term|quiz", re.I)
_RE_TAIL  = re.compile(r"^(.*?)[\s.:#-]*(\d+)\s*$")     # 'LAB 12' -> ('LAB', 12)

_RUN_MIN  = 4        # run ngắn hơn thế thì in bình thường (ca 1–3 điểm phải NGẮN như cũ)
_WIDTH    = 72       # bề ngang tối đa 1 dòng nối bằng ' · ' (chat, không căn cột)

def _bucket_of(item):
    """Đầu điểm -> tên nhóm. 'final' xét TRƯỚC (giữ đúng thói quen cũ: thi cuối kỳ luôn ở cuối khối)."""
    s = str(item or "")
    if "final" in s.lower():
        return "final"
    if _RE_LAB.search(s):
        return "lab"
    if _RE_PROG.search(s):
        return "prog"
    return "other"

def _split_num(name):
    """'LAB 12' -> ('LAB', 12); không có số ở đuôi -> None."""
    m = _RE_TAIL.match(str(name or ""))
    if not m:
        return None
    pre = m.group(1).strip()
    return (pre, int(m.group(2))) if pre else None

def _mode(values):
    """Giá trị XUẤT HIỆN NHIỀU NHẤT nếu nó chiếm ĐA SỐ THẬT (>50%), còn lại None = 'không có chủ đạo'."""
    best, cnt = None, 0
    for v in values:
        c = values.count(v)
        if c > cnt:
            best, cnt = v, c
    return best if cnt >= 2 and cnt * 2 > len(values) else None

def _collapse_run(prefix, got):
    """got: [(số, TÊN THẬT, giá trị)] cùng tiền tố -> 1 dòng 'chủ đạo + ngoại lệ', None nếu không gộp được.

    Dải chỉ ghi 'a–b' khi các số LIÊN TIẾP **và không trùng nhau** — 'LAB 1' với 'Lab 1' là hai đầu
    điểm KHÁC nhau nhưng cùng số, gộp thành dải sẽ khẳng định một con điểm chưa từng nhận. Ngoại lệ
    in bằng TÊN THẬT của mục (không ghép lại từ prefix) để không đổi hoa/thường của người ta."""
    if len(got) < _RUN_MIN:
        return None
    got  = sorted(got, key=lambda p: p[0])
    nums = [n for n, _, _ in got]
    mode = _mode([v for _, _, v in got])
    if mode is None:                       # mỗi mục một giá trị -> gộp lại chẳng ngắn hơn, in thường
        return None
    uniq = sorted(set(nums))
    contiguous = len(uniq) == len(nums) and uniq[-1] - uniq[0] + 1 == len(uniq)
    span = f"{uniq[0]}–{uniq[-1]}" if contiguous else ",".join(str(n) for n in nums)
    head = t(f"{prefix} {span}: toàn {mode}", f"{prefix} {span}: all {mode}")
    exc  = [f"{name}: {v}" for _, name, v in got if v != mode]
    return head + ("  ·  " + " · ".join(exc) if exc else "")

def _pack(pieces):
    """Nối các mẩu bằng ' · ' trên CÙNG 1 dòng, xuống dòng khi quá rộng (nhóm ít mục -> đúng 1 dòng)."""
    lines, cur = [], ""
    for p in pieces:
        cand = p if not cur else cur + " · " + p
        if cur and len(cand) > _WIDTH:
            lines.append(cur); cur = p
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines

def _bucket_lines(emoji, entries):
    """entries: [(tên, giá trị)] đã sort tự nhiên -> các dòng đã thụt lề, dòng ĐẦU mang emoji nhóm."""
    runs, order = {}, []
    for name, val in entries:
        sp = _split_num(name)
        key = sp[0].lower() if sp else None
        if key is None:
            key = ("\x00single", name)          # mục không đánh số: mỗi mục 1 nhóm riêng
        if key not in runs:
            runs[key] = (sp[0] if sp else name, [])
            order.append(key)
        runs[key][1].append((sp[1] if sp else None, name, val))
    body, pend = [], []
    for key in order:
        prefix, got = runs[key]
        line = _collapse_run(prefix, got) if got[0][0] is not None else None
        if line:
            body += _pack(pend); pend = []      # giữ đúng thứ tự: xả các mục lẻ trước dòng gộp
            body.append(line)
        else:
            pend += [f"{name}: {val}" for _, name, val in got]
    body += _pack(pend)
    return [f"   {emoji} {l}" if i == 0 else f"      {l}" for i, l in enumerate(body)]

def render_events(events):
    """THUẦN: [{subj,item,value}] -> chuỗi ĐẸP. Gom theo MÔN (giữ thứ tự môn xuất hiện), trong môn chia
    NHÓM 🔬 Lab / 📝 Progress / 📎 Khác / 🏁 Final, sort đầu điểm tự nhiên, run dài gộp 'chủ đạo + ngoại lệ';
    item=None = điểm tổng kết môn (để CUỐI khối). Rỗng -> ''.

    Header môn BẮT BUỘC mang số điểm mới: 'LAB 1–12' chỉ là các lab VỪA ĐỔI, không phải toàn bộ lab của môn."""
    by_subj = {}
    for e in events:
        by_subj.setdefault(e.get("subj", ""), []).append(e)
    blocks = []
    for subj, items in by_subj.items():
        comps  = [e for e in items if e.get("item") is not None]
        finals = [e for e in items if e.get("item") is None]
        n = len(items)
        lines = [t(f"📘 {subj} · {n} điểm mới", f"📘 {subj} · {n} new mark" + ("s" if n != 1 else ""))]
        for key, emoji in _BUCKETS:
            grp = sorted(((str(e["item"]), str(e["value"])) for e in comps if _bucket_of(e["item"]) == key),
                         key=lambda p: _natkey(p[0]))
            if grp:
                lines += _bucket_lines(emoji, grp)
        lines += [t(f"   ★ Điểm tổng kết: {e['value']}", f"   ★ Final mark: {e['value']}") for e in finals]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)

def _load_state():
    if not os.path.exists(STATE):
        return {}
    try:
        with open(STATE, encoding="utf-8") as f:          # ĐÓNG handle trước os.replace (Windows không rename file đang mở)
            return json.load(f)
    except (ValueError, OSError):
        try: os.replace(STATE, STATE + ".corrupt")
        except OSError: pass
        print(t("⚠️ grade_state.json hỏng → thiết lập lại baseline.",
                "⚠️ grade_state.json corrupt → rebaselining."))
        return {}

def _save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = f"{STATE}.{os.getpid()}.tmp"           # tên RIÊNG theo tiến trình: 2 service cùng profile
    with open(tmp, "w", encoding="utf-8") as f:  # khởi động sát nhau không ghi đè tmp của nhau
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)
    # Dưới profile, file này là điểm thành phần của NGƯỜI KHÁC -> hạn quyền như auth/gcal/attendwatch.
    try: os.chmod(STATE, 0o600)
    except OSError: pass

def poll(notify=True):
    """1 lượt dò. Trả số điểm mới phát hiện."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    marks = fetch_marks(token, campus, roll, sem)        # đã check_auth -> token hết hạn sẽ raise
    if not marks:
        print(t("(Chưa có môn nào trong kỳ — bỏ qua lượt này.)", "(No subjects this term — skipping.)"))
        return 0
    detail_fn = lambda subj, cid: fetch_components(token, campus, roll, cid, subj)
    events, new_state, first_run = compute(marks, detail_fn, _load_state())
    # Lần đầu mà MỌI môn lấy chi tiết hỏng -> new_state {} -> lần sau lại tưởng first-run mãi.
    # Ghi 1 sentinel để state thành non-empty (khoá '__baselined__' không trùng subjectCode nào).
    _save_state(new_state if new_state else {"__baselined__": {}})
    if first_run:
        print(t(f"👀 Bắt đầu theo dõi điểm ({len(marks)} môn). Sẽ báo khi có điểm mới.",
                f"👀 Now watching grades ({len(marks)} subjects). You'll get a ping on each new mark."))
        return 0
    if not events:
        print(t("Chưa có điểm mới.", "No new marks.")); return 0
    msg = fmt.header("🎯", t("Có điểm mới!", "New marks!")) + "\n" + render_events(events)
    print(msg)
    if notify:
        sent = push(msg)
        print(t("→ Đã gửi tới:", "→ Sent to:"), sent or t("(chưa cấu hình kênh — sửa .env)", "(no channel — edit .env)"))
    return len(events)

def loop(interval_min=30, refresh_min=50):
    try: interval_min = int(interval_min)
    except (TypeError, ValueError):
        print(t("Số phút không hợp lệ, dùng 30.", "Invalid minutes, using 30.")); interval_min = 30
    interval_min = max(interval_min, 10)                 # điểm đổi chậm -> tối thiểu 10' (nhẹ server)
    print(t(f"👀 Theo dõi điểm mỗi {interval_min}' (06:00–22:00 giờ VN); tự refresh token ~{refresh_min}'. Ctrl+C để dừng.",
            f"👀 Watching grades every {interval_min}m (06:00–22:00 VN); auto token-refresh ~{refresh_min}m. Ctrl+C to stop."))
    if autoupdate_min():
        print(t(f"🔄 Tự cập nhật khi đang chạy: BẬT mỗi {autoupdate_min()}' (FAP_AUTOUPDATE_MIN).",
                f"🔄 Update-while-running: ON every {autoupdate_min()}m (FAP_AUTOUPDATE_MIN)."))
    last_update = 0.0
    # Ngủ vài giây (dải riêng ở _stagger) RỒI refresh ngay vòng đầu — lệch với attendwatch/reminders
    # mà lần poll ĐẦU vẫn có token còn hạn (vòng lặp này tới 60' nên hoãn refresh sang vòng sau là quá muộn).
    time.sleep(startup_delay("gradewatch"))
    last_refresh = 0.0
    while True:
        last_update = maybe_autoupdate(last_update, time.time())   # opt-in: pull+selftest → tự restart
        if 6 <= _vn_now().hour <= 22:
            if time.time() - last_refresh > refresh_min * 60:   # giữ token sống cho service chạy nền
                _refresh_token()
                last_refresh = time.time()       # LUÔN dời mốc dù refresh fail -> không spam /connect/token
            try:
                poll(notify=True)
            except SystemExit as e:
                print(t("  (bỏ qua lượt này) ", "  (skipping this round) "), e)
            except Exception as e:                        # noqa: BLE001 — đừng chết vì 1 lượt
                print("  lỗi · error:", e)
        time.sleep(interval_min * 60)

def run(args=None):
    args = args or []
    if args and str(args[0]).lstrip("-").lower() == "loop":
        loop(args[1] if len(args) > 1 else 30)
    else:
        poll(notify=True)

def main():
    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        print("\nĐã dừng.")
        sys.exit(0)

if __name__ == "__main__":
    main()
