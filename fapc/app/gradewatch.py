#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gradewatch.py — Báo khi có ĐIỂM MỚI (thành phần hoặc tổng kết) — near real-time.

    fap watch-grades              # 1 lượt: dò thay đổi -> báo lên kênh -> thoát (cho cron)
    fap watch-grades loop [phút]  # chạy nền, dò mỗi <phút> (mặc định 30), 06:00–22:00 giờ VN

Giống watch-attendance: FAP không đẩy cho mình -> phải POLL. So GetStudentMark (+ GetMarkByCourse
cho điểm thành phần) với lần trước; chỉ báo phần MỚI/ĐỔI. Mỗi điểm chỉ báo ĐÚNG 1 LẦN
(nhớ trong output/grade_state.json). Im lặng khi không có gì mới.
"""
import os, sys, json, time
from ..core.api import creds, current_semester, _vn_now
from ..core.grades import fetch_marks, fetch_components
from .notify import push
from .attendwatch import _refresh_token          # dùng chung: tự làm mới token cho service chạy nền
from ..i18n import t
from .. import fmt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(_ROOT, "output", "grade_state.json")

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
                    events.append(f"• {subj} · {k}: {v}")
            oa, na = prev.get("avg", ""), snap["avg"]   # so theo SỐ -> '8.5' vs '8.50' không báo nhầm
            if fmt.safe_float(na) > 0 and fmt.safe_float(na) != fmt.safe_float(oa):
                events.append(t(f"• {subj} · điểm tổng kết: {na}", f"• {subj} · final mark: {na}"))
        new_state[subj] = snap
    return events, new_state, first_run

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
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE)

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
    msg = fmt.header("🎯", t("Có điểm mới!", "New marks!")) + "\n" + "\n".join(events)
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
    last_refresh = 0.0
    while True:
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
