#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attendance.py — điểm danh (GetStudentAttendances) + cảnh báo nguy cơ cấm thi.

Thêm (THUẦN, test offline được):
  • trạng thái điểm danh TỪNG BUỔI từ lịch học (GetActivityStudent.attendanceStatus) -> ngày vắng theo môn
  • giai đoạn môn theo startDate/endDate (GetStudentAttendances) -> 'chưa bắt đầu' / 'đã kết thúc' / 'còn N ngày'
"""
from .api import creds, call, as_list, current_semester, check_auth, _vn_now
from . import subjects
from .schedule import parse_date
from ..i18n import t

# FPT: vắng > 20% tổng buổi -> cấm thi. Proxy theo % chuyên cần hiện tại.
BAN_THRESHOLD = 80   # < 80% chuyên cần = nguy cơ

def fetch(token, campus, roll, sem):
    http, data = call("GetStudentAttendances",
        [("campusCode", campus), ("Authen", token), ("Semester", sem), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _pct(r):
    """% chuyên cần. None nếu CHƯA có dữ liệu (rỗng/None) — KHÁC với 0% thật."""
    v = r.get("attendance")
    if v in (None, ""):
        return None
    try: return float(v)
    except (TypeError, ValueError): return None

# ---------- trạng thái TỪNG BUỔI (lịch học) ----------
# Mã `attendanceStatus` của GetActivityStudent, lấy ĐÚNG theo app chính thức (hàm getAttendanceStatus trong
# bundle): 'P' -> có mặt, 'A' -> vắng, mọi giá trị khác (thực tế 'N') -> "chưa diễn ra". KHÔNG có mã "muộn".
# Nhận thêm dạng chữ đầy đủ của getCourseAttendance ('Present'/'Absent') cho chắc.
_PRESENT, _ABSENT = frozenset({"p", "present"}), frozenset({"a", "absent"})

def session_status(s):
    """THUẦN: 'present' | 'absent' | None (chưa diễn ra / chưa điểm danh / mã lạ — KHÔNG đoán)."""
    v = str((s or {}).get("attendanceStatus") or "").strip().lower()
    return "present" if v in _PRESENT else ("absent" if v in _ABSENT else None)

def att_tail(s):
    """THUẦN: đuôi gắn vào dòng buổi học: '  ✅' có mặt · '  ❌' vắng · '' chưa diễn ra/chưa điểm danh.
    Buổi tương lai luôn 'N' -> không có dấu gì, nên chỉ buổi ĐÃ QUA mới hiện ✅/❌."""
    st = session_status(s)
    return "  ✅" if st == "present" else ("  ❌" if st == "absent" else "")

def recorded_by_subject(sessions):
    """THUẦN: {mã môn: số buổi ĐÃ điểm danh (có mặt + vắng)}.

    Môn chỉ có mặt trong kết quả khi FAP THỰC SỰ trả mã trạng thái (P/A/N…) cho buổi của nó. Nếu field
    vắng hẳn (shape cũ / endpoint khác) thì môn KHÔNG có trong dict -> caller nhận None -> KHÔNG được coi là
    'chưa điểm danh buổi nào' (0) — nếu không, thiếu dữ liệu sẽ giấu mất cảnh báo cấm thi thật."""
    out = {}
    for s in sessions or []:
        if isinstance(s, dict) and s.get("subjectCode") and str(s.get("attendanceStatus") or "").strip():
            out.setdefault(s["subjectCode"], 0)
            if session_status(s):
                out[s["subjectCode"]] += 1
    return out

def absences_by_subject(sessions):
    """THUẦN: {mã môn: [date đã vắng, …] tăng dần}. Chỉ buổi có mã 'A' (vắng) và parse được ngày."""
    out = {}
    for s in sessions or []:
        if isinstance(s, dict) and session_status(s) == "absent":
            d = parse_date(s.get("date"))
            if d:
                out.setdefault(s.get("subjectCode", ""), []).append(d)
    return {k: sorted(v) for k, v in out.items()}

def absence_line(dates):
    """THUẦN: '❌ Vắng 2: 12/06, 19/06' ('' nếu không vắng buổi nào)."""
    if not dates:
        return ""
    ds = ", ".join(d.strftime("%d/%m") for d in dates)
    return t(f"❌ Vắng {len(dates)}: {ds}", f"❌ Absent {len(dates)}: {ds}")

# ---------- giai đoạn môn (startDate / endDate) ----------
def phase(r, today):
    """THUẦN: 'not_started' | 'ongoing' | 'ended' theo startDate/endDate; None nếu thiếu/không đọc được
    (lúc đó mọi hiển thị/cảnh báo giữ NGUYÊN như trước)."""
    if not today:
        return None
    start, end = parse_date(r.get("startDate")), parse_date(r.get("endDate"))
    if start and today < start:
        return "not_started"
    if end and today > end:
        return "ended"
    if start or end:
        return "ongoing"
    return None

def _eff_phase(r, today, recorded=None):
    """phase() nhưng FAIL-SAFE: lịch học đã có buổi P/A cho môn (recorded > 0) thì môn CHẮC CHẮN đã bắt đầu,
    dù startDate nói khác (vd ngày dd/mm bị đọc thành mm/dd). Khi đó KHÔNG tin 'not_started' (-> None =
    hiển thị/cảnh báo như cũ), để một ngày tháng đọc sai không bao giờ giấu được cảnh báo cấm thi thật."""
    ph = phase(r, today)
    return None if (ph == "not_started" and recorded) else ph

def att_state(r, today, recorded=None):
    """THUẦN: nhãn ngắn giai đoạn môn cho chat ('' nếu không có gì đáng nói).
    `recorded` = số buổi đã điểm danh của môn (từ lịch học) — 0 nghĩa là % hiện tại CHƯA có ý nghĩa."""
    ph = _eff_phase(r, today, recorded)
    if ph == "not_started":
        start = parse_date(r.get("startDate"))
        return t(f"⏳ chưa bắt đầu (từ {start:%d/%m})", f"⏳ not started (from {start:%d/%m})")
    if ph == "ended":
        return t("✔ đã kết thúc", "✔ ended")
    if recorded == 0:
        return t("chưa điểm danh buổi nào", "no session recorded yet")
    if ph == "ongoing":
        end = parse_date(r.get("endDate"))
        if end:
            left = (end - today).days                     # endDate là ngày học CUỐI (phase coi là 'ongoing')
            if left <= 0:
                return t("hôm nay là ngày cuối", "last day today")
            return t(f"còn {left} ngày", f"{left} day left" if left == 1 else f"{left} days left")
    return ""

def _at_risk(r, today=None, recorded=None):
    """True nếu môn có nguy cơ cấm thi. Môn CHƯA có dữ liệu (None) -> KHÔNG tính nguy cơ.

    Hai tham số TUỲ CHỌN (không truyền = y hệt hành vi cũ, kể cả '0% thật vẫn là nguy cơ'):
      • today    — môn CHƯA BẮT ĐẦU (today < startDate) -> không nguy cơ (0% lúc đầu kỳ là vô nghĩa)
      • recorded — số buổi đã điểm danh theo lịch học (mã P/A); 0 -> chưa có gì để đánh giá -> không nguy cơ.
    CỐ Ý không dùng numberOfTakenAttendances==0: chưa chắc field đó đếm buổi ĐÃ ĐIỂM DANH hay buổi CÓ
    MẶT — nếu là 'có mặt' thì SV vắng hết mọi buổi (0% thật) sẽ bị giấu mất cảnh báo."""
    if today is not None and _eff_phase(r, today, recorded) == "not_started":
        return False
    if recorded == 0:
        return False
    p = _pct(r)
    return p is not None and p < BAN_THRESHOLD

def attendance_lines(rows, today=None, sessions=None, label=None):
    """THUẦN: các dòng '• <môn> — <%>  (x/y) · <giai đoạn>' + dòng ngày vắng, dùng CHUNG cho bot và CLI.
    `sessions` (lịch học) là tuỳ chọn: có thì thêm ngày vắng + nhận biết môn chưa điểm danh buổi nào.
    `label` = hàm mã môn -> nhãn hiển thị (mặc định subjects.label)."""
    label = label or subjects.label
    rec = recorded_by_subject(sessions) if sessions is not None else {}
    absn = absences_by_subject(sessions) if sessions is not None else {}
    out = []
    for r in rows:
        code = r.get("subjectCode", "")
        recorded = rec.get(code) if sessions is not None and code in rec else None
        ph = _eff_phase(r, today, recorded)
        taken, total = r.get("numberOfTakenAttendances"), r.get("numberOfAttendances")
        if ph == "not_started":
            body = att_state(r, today, recorded)                 # 0% lúc chưa học là vô nghĩa -> không in %
        else:
            warn = " ⚠️" if _at_risk(r, today, recorded) else ""
            cnt = f"  ({taken}/{total})" if taken is not None and total is not None else ""
            pct = r.get("attendance", "")
            state = att_state(r, today, recorded)
            body = f"{pct}%{warn}{cnt}" + (f"  ·  {state}" if state else "")
        out.append(f"• {label(code)} — {body}")
        ab = absence_line(absn.get(code))
        if ab:
            out.append(f"   {ab}")
    return out

def sessions_or_none(token, campus, roll, sem):
    """Lịch học cả kỳ để lấy trạng thái từng buổi; None nếu lấy không được (mạng/…): màn điểm danh vẫn
    phải hiện được — chỉ thiếu ngày vắng. Tốn THÊM 1 request GetActivityStudent (api.call chỉ cache khi
    FAP_CACHE_MIN>0 — mặc định TẮT), nên chỉ gọi khi thật sự cần."""
    try:
        from .schedule import fetch_sessions
        return fetch_sessions(token, campus, roll, sem)
    except (Exception, SystemExit):                    # noqa: BLE001 — phần PHỤ: kể cả lỗi token (SystemExit)
        return None                                    # cũng không được làm sập màn điểm danh chính

def report():
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    subjects.load()                                   # tên môn từ cache (nếu đã `fap subjects`)
    rows = fetch(token, campus, roll, sem)
    print(t(f"== Điểm danh kỳ {sem} ==", f"== Attendance {sem} =="))
    if not rows:
        print(t("(Chưa có dữ liệu điểm danh.)", "(No attendance yet.)")); return
    # Dùng CHUNG renderer với bot (attendance_lines) -> CLI và chat luôn khớp nhau.
    print("\n".join(attendance_lines(rows, _vn_now().date(), sessions_or_none(token, campus, roll, sem))))

def banrisk():
    """In các môn nguy cơ cấm thi. Trả exit code 2 nếu có nguy cơ (cho cron/CI)."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = fetch(token, campus, roll, sem)
    at_risk = []
    # Không môn nào dưới ngưỡng THÔ (_at_risk không tham số) -> chắc chắn an toàn, KHỎI tốn thêm request lịch:
    # lịch chỉ dùng để BỚT cảnh báo nhầm (và fail-safe trả lại cảnh báo thô), không bao giờ thêm môn mới.
    if any(_at_risk(r) for r in rows):
        today, sess = _vn_now().date(), sessions_or_none(token, campus, roll, sem)
        rec = recorded_by_subject(sess) if sess is not None else {}
        at_risk = [r for r in rows if _at_risk(r, today, rec.get(r.get("subjectCode")))]
    if not at_risk:
        print(t("✓ Không môn nào nguy cơ cấm thi (chuyên cần ≥ 80%).",
                "✓ No exam-ban risk (attendance ≥ 80%).")); return 0
    print(t("⚠️  NGUY CƠ CẤM THI (chuyên cần < 80%):", "⚠️  EXAM-BAN RISK (attendance < 80%):"))
    for r in at_risk:
        print(f"   {r.get('subjectCode','')}: {r.get('attendance','')}%")
    return 2
