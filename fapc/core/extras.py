#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extras.py — tra cứu nhỏ: lịch thi, tin tức, học phí/số dư.

    fap exams   # GetScheduleExam   (cũng dùng cho `fap notify exams` + bot /exams)
    fap news    # GetTop10News
    fap fees    # GetBalance + GeFeeByRoll + link hoá đơn điện tử (CHỈ CLI — link chứa MSSV)
    fap todo    # CheckOpenFeedBack + CheckUpdateProfile + GetApplication ('3' chờ thanh toán) — việc phải TỰ làm

Endpoint có thể RỖNG/404 với tài khoản chưa tới kỳ thi / chưa có dữ liệu — xử lý rỗng đàng hoàng.
"""
import os, re, datetime, urllib.parse
from .api import creds, call, unwrap, as_list, current_semester, checksum_auth, check_auth, _vn_now
from . import subjects, paths, apiv2
from ..i18n import t
from .. import fmt

# ---------- HỒ SƠ SINH VIÊN (GetStudentById) ----------
_PROFILE_ROWS = [            # (key, nhãn_vi, nhãn_en) — chỉ hiện field có giá trị
    ("rollNumber", "MSSV", "Roll"), ("email", "Email", "Email"),
    ("dateOfBirth", "Ngày sinh", "DOB"), ("gender", "Giới tính", "Gender"),
    ("major", "Ngành", "Major"), ("nganh", "Ngành", "Major"), ("chuyenNganh", "Chuyên ngành", "Specialization"),
    ("batch", "Khoá", "Batch"), ("lopchinh", "Lớp", "Class"), ("currentTermNo", "Kỳ hiện tại", "Term"),
    ("mobilePhone", "SĐT", "Phone"), ("iDCard", "CCCD", "ID card"), ("statusCode", "Trạng thái", "Status"),
]
# Field NHẠY CẢM: chỉ in ở CLI (máy của chính bạn). Bot/web mặc định ẨN — tin chat nằm lại trên máy chủ
# Telegram/Discord và mọi thiết bị đăng nhập. Mặc định full=False để đường mới nào quên truyền cờ vẫn AN TOÀN.
_PROFILE_PRIVATE = ("dateOfBirth", "mobilePhone", "iDCard")

def fetch_profile(token, campus, roll):
    http, data = call("GetStudentById", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def profile_text(token, campus, roll, full=False):
    """full=True chỉ cho CLI (`fap profile`): hiện thêm ngày sinh/SĐT/CCCD. Chat gọi mặc định -> ẩn."""
    rows = fetch_profile(token, campus, roll)
    if not rows or not isinstance(rows[0], dict):
        return t("👤 Không lấy được hồ sơ.", "👤 Couldn't fetch profile.")
    r = rows[0]
    out = [fmt.header("👤", fmt.unescape(r.get("fullname")) or t("Hồ sơ", "Profile"), fmt.unescape(r.get("rollNumber")))]
    seen = set()
    for key, vi, en in _PROFILE_ROWS:
        if key in _PROFILE_PRIVATE and not full:
            continue
        if key == "dateOfBirth":
            v = fmt.fmt_date(r["dateOfBirth"]) if r.get("dateOfBirth") else ""
        elif key == "gender":
            g = r.get("gender")
            v = "" if g in (None, "") else (t("Nam", "Male") if g in (True, "true", "True", 1, "1") else t("Nữ", "Female"))
        else:
            v = fmt.unescape(r.get(key))
        label = t(vi, en)
        if v and label not in seen:          # 'major'/'nganh' cùng nhãn 'Ngành' -> chỉ hiện 1
            seen.add(label); out.append(f"• {label}: {v}")
    if not full:
        out.append(t("🔒 Ngày sinh · SĐT · CCCD không gửi lên chat — xem trên máy: fap profile",
                     "🔒 Date of birth · phone · ID card are not sent to chat — view locally: fap profile"))
    return "\n".join(out)

def profile():
    token, campus, roll = creds()
    print(profile_text(token, campus, roll, full=True))

# ---------- ĐƠN TỪ (GetApplication) ----------
def _appl_date(r):
    raw = str(r.get("createDate") or "").split("T")[0].split(" ")[0]
    for f in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(raw, f).date()
        except ValueError: continue
    return None

def fetch_applications(token, campus, roll):
    http, data = call("GetApplication", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

# Mã `studentStatus` của GetApplication, lấy ĐÚNG theo app chính thức (hàm getStatusConfig + bảng i18n
# lb_appli_status_*), bản myFAP 2.0.5 (versionCode 29):
#   '0' Đang xử lý · '1' Đã được chấp nhận · '2' Hủy · '3' Đang chờ thanh toán · mã khác -> "Khác".
# ⚠️ Bản 2.0.4 chỉ có nhánh '0'/'1' và cho MỌI mã khác rơi vào "Đã bị từ chối" — vì vậy '2' TỪNG hiện là
# "từ chối". 2.0.5 sửa '2' thành "Hủy", thêm '3', và bỏ hẳn nhãn "từ chối" khỏi getStatusConfig. Đừng quay lại
# cách đọc cũ: một lá đơn bị HỦY mà báo là bị TỪ CHỐI là thông tin sai.
_APP_STATUS = {"0": ("⏳", "Đang xử lý", "Processing"),
               "1": ("✅", "Đã được chấp nhận", "Approved"),
               "2": ("🚫", "Đã hủy", "Cancelled"),
               "3": ("💳", "Đang chờ thanh toán", "Pending payment")}

def app_status(r):
    """THUẦN: nhãn trạng thái đơn có icon ('' nếu server không gửi trạng thái).
    Mã ngoài bảng -> '❔ Khác (mã N)' — khớp nhãn "Khác/Other" của app 2.0.5, kèm mã để tra cứu."""
    raw = r.get("studentStatus")
    v = str(raw if raw is not None else "").strip()          # int 0 phải thành '0', không được rơi mất
    if not v:
        return ""
    if v in _APP_STATUS:
        icon, vi, en = _APP_STATUS[v]
        return f"{icon} {t(vi, en)}"
    return t(f"❔ Khác (mã {v})", f"❔ Other (code {v})")

def _app_tally(rows):
    """THUẦN: '⏳1 ✅1 🚫2' — đếm theo trạng thái cho dòng tiêu đề ('' nếu không đơn nào có trạng thái)."""
    counts = {}
    for r in rows:
        v = str(r.get("studentStatus") if r.get("studentStatus") is not None else "").strip()
        if v in _APP_STATUS:
            counts[v] = counts.get(v, 0) + 1
    return " ".join(f"{_APP_STATUS[k][0]}{counts[k]}" for k in _APP_STATUS if k in counts)

def applications_text(token, campus, roll):
    rows = [r for r in fetch_applications(token, campus, roll) if isinstance(r, dict)]
    if not rows:
        return t("📄 Chưa có đơn từ nào.", "📄 No applications.")
    rows.sort(key=lambda r: _appl_date(r) or datetime.date.min, reverse=True)   # mới nhất trước
    tally = _app_tally(rows)
    out = [fmt.header("📄", t("Đơn từ", "Applications"), str(len(rows)) + (f"  ·  {tally}" if tally else ""))]
    for r in rows:
        name = fmt.unescape(r.get("name")) or t("(đơn)", "(application)")
        date = fmt.unescape(r.get("createDate"))
        out.append(f"\n• {name}" + (f"  ·  {date}" if date else ""))
        st = app_status(r)                                   # trạng thái xử lý (lệnh này hứa hiện từ lâu)
        if st:
            out.append(f"   {st}")
        note = fmt.unescape(r.get("processNote"))           # phản hồi của phòng ban (decode &#xxx;)
        if note:
            out.append(f"   ↳ {note}")
    return "\n".join(out)

def applications():
    token, campus, roll = creds()
    print(applications_text(token, campus, roll))

def _fetch_ok(endpoint, token, campus, roll):
    """GET 1 endpoint ký cs12(rollNumber, campusCode) với 3 tham số campusCode/Authen/rollNumber (như
    extract.SIMPLE) -> (True, data) khi HTTP 200 + code '200'; (False, None) khi lỗi mạng / phản hồi lạ.
    Khác fetch_*: lỗi mạng KHÔNG bị biến thành [] ("không có gì") — người gọi phân biệt được "KHÔNG BIẾT".
    Lỗi XÁC THỰC vẫn raise qua check_auth (token hết hạn) để người gọi ghi lại lý do."""
    http, data = call(endpoint, [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    if http != 200 or not isinstance(data, dict) or str(data.get("code")) != "200":
        return False, None
    return True, data.get("data")

def fetch_applications_checked(token, campus, roll):
    """Đơn từ cho cảnh báo/to-do: list dict khi lấy ĐƯỢC (rỗng = thật sự không có đơn), None khi KHÔNG BIẾT."""
    ok, d = _fetch_ok("GetApplication", token, campus, roll)
    if not ok:
        return None
    if d is None:
        return []
    return [r for r in d if isinstance(r, dict)] if isinstance(d, list) else None

# ---------- ĐƠN TỪ ĐỔI TRẠNG THÁI (đẩy cùng nhịp `fap notify notifications`) ----------
def _app_id(r):
    """Khoá ỔN ĐỊNH của 1 lá đơn = mã đơn của server. v1 trả 'w_APP_ID' (analysis/keys_schema.py: có ở 4/4
    đơn), còn app 2.0.5 đọc 'w_app_id' (sắp đơn theo số này + hiện '#…') ⇒ dò KHÔNG phân biệt hoa/thường.
    '' nếu thiếu -> lá đơn đó không theo dõi được (KHÔNG đoán bằng vị trí hay tên đơn)."""
    if not isinstance(r, dict):
        return ""
    for k, v in r.items():
        if str(k).lower() == "w_app_id" and v is not None and str(v).strip():
            return str(v).strip()
    return ""

def _app_code(r):
    """THUẦN: mã studentStatus dạng chuỗi đã strip ('' nếu thiếu) — int 3 và '3' là MỘT mã."""
    raw = r.get("studentStatus") if isinstance(r, dict) else None
    return str(raw if raw is not None else "").strip()

def _code_label(code):
    """Nhãn có icon của 1 MÃ trạng thái (dùng lại app_status/_APP_STATUS); mã rỗng -> '❔ chưa rõ'."""
    return app_status({"studentStatus": code}) or t("❔ chưa rõ", "❔ unknown")

def app_changes(prev_state, rows):
    """THUẦN: so trạng thái đơn từ với mốc lần trước -> (new_state, changes).
      prev_state : {mã_đơn: mã_trạng_thái} hoặc None (CHƯA ghi mốc lần nào)
      rows       : các dòng GetApplication lấy THÀNH CÔNG ở lượt này
      new_state  : mốc mới để lưu
      changes    : [{"id","name","date","note","old","new"}]; old=None = đơn MỚI xuất hiện sau mốc.
                   Xếp: → '3' (cần thanh toán) trước, → '1' (được chấp nhận) sau đó, rồi phần còn lại.
    Luật: lần đầu = ghi mốc IM LẶNG · đơn biến mất = bỏ khỏi mốc, KHÔNG báo · danh sách RỖNG trong khi mốc đang
    có đơn = coi là trục trặc tạm thời, GIỮ mốc cũ · đơn mất trạng thái ('') = giữ mã cũ, KHÔNG báo."""
    cur, by_id = {}, {}
    for r in rows or []:
        aid = _app_id(r)
        if aid:
            cur[aid], by_id[aid] = _app_code(r), r
    if prev_state is None:
        return cur, []
    prev = {str(k): str(v if v is not None else "").strip() for k, v in prev_state.items()}
    if not cur and prev:
        return prev, []
    changes = []
    for aid, code in list(cur.items()):
        old = prev.get(aid)
        if old is not None and not code:
            cur[aid] = old                     # server tạm không gửi trạng thái -> giữ mã cũ, không báo nhầm
            continue
        if old == code:
            continue
        r = by_id[aid]
        changes.append({"id": aid, "name": fmt.unescape(r.get("name")), "date": fmt.unescape(r.get("createDate")),
                        "note": fmt.unescape(r.get("processNote")), "old": old, "new": code})
    rank = {"3": 0, "1": 1}
    changes.sort(key=lambda c: rank.get(c["new"], 2))     # sort ổn định: cùng hạng giữ thứ tự server
    return cur, changes

def app_changes_text(changes):
    """THUẦN: tin đẩy cho các đơn ĐỔI trạng thái ('' nếu không có gì). Đổi sang '3' (cần thanh toán) và '1'
    (được chấp nhận) được làm NỔI (đứng đầu + dòng hành động); đơn MỚI hiện trạng thái hiện tại."""
    if not changes:
        return ""
    out = [fmt.header("📄", t("Đơn từ đổi trạng thái", "Application status changes"), str(len(changes)))]
    for c in changes:
        name = c.get("name") or t("(đơn)", "(application)")
        if c.get("date"):
            name += f" ({c['date']})"         # 2 đơn cùng loại -> phân biệt bằng ngày tạo
        lead = {"3": "‼️ ", "1": "🎉 "}.get(c.get("new"), "")
        new = _code_label(c.get("new"))
        if c.get("old") is None:
            out.append(f"{lead}🆕 📄 {name} · {new}")
        else:
            out.append(f"{lead}📄 {name} · {_code_label(c['old'])} → {new}")
        if c.get("new") == "3":
            # Màn đơn từ của app 2.0.5 KHÔNG có nút thanh toán (chỉ hiện nhãn) -> chỉ nêu kênh chính thức, không bịa
            out.append("   " + t("👉 CẦN THANH TOÁN — xem & thanh toán qua kênh chính thức (app myFAP / fap.fpt.edu.vn); fap-cli chỉ đọc.",
                                "👉 PAYMENT NEEDED — check and pay via the official channels (myFAP app / fap.fpt.edu.vn); fap-cli is read-only."))
        elif c.get("new") == "1":
            out.append("   " + t("👉 Đơn đã được CHẤP NHẬN.", "👉 Application APPROVED."))
        note = _preview(c.get("note") or "")              # phản hồi của phòng ban (1 dòng trích)
        if note:
            out.append(f"   ↳ {note}")
    return "\n".join(out)

# ---------- VIỆC CẦN LÀM · TO-DO (feedback đang mở · cập nhật hồ sơ · đơn chờ thanh toán) ----------
# fap-cli CHỈ ĐỌC: mỗi mục chỉ NHẮC sinh viên tự làm qua kênh chính thức — KHÔNG BAO GIỜ gọi AddRate /
# SubmitStudentFeedback. GetStudentRate KHÔNG dùng: nghĩa các trường của nó chưa kiểm chứng.
def _feedback_open(v):
    """THUẦN: CheckOpenFeedBack.data -> True (đợt feedback đang mở) / False (không) / None (KHÔNG BIẾT).
    App 2.0.5 (màn Lịch học: `r == 'true' || r == true`) nhận cả boolean lẫn CHUỖI 'true' -> nhận cả hai, không
    phân biệt hoa/thường. Ngoài đợt server trả false hoặc '' (docs/03-extraction-catalog)."""
    if v is True:
        return True
    if v is False:
        return False
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "true":
            return True
        if s in ("false", ""):
            return False
    return None

def _profile_needs_update(v):
    """THUẦN: CheckUpdateProfile.data -> True (PHẢI cập nhật hồ sơ) / False / None (KHÔNG BIẾT).
    Theo myFAP 2.0.5 (4 màn Lịch học · Lịch tuần · Điểm · Điểm danh): `hasUpdateProfile = (data == false)` rồi hiện
    "You need to update your profile at FAP. Please access https://fap.fpt.edu.vn". Khi lỗi, lớp API của app trả ''
    (mà '' == false trong JS ⇒ app có thể nhắc NHẦM) — ở đây CHỈ boolean false mới tính; rỗng/lỗi/lạ = không biết."""
    if v is False:
        return True
    if v is True:
        return False
    return None

def _profile_flag_v2(v):
    """THUẦN: API v2 trả CheckUpdateProfile khác v1 — adapter v2 của app 2.0.5 đổi `data` thành
    `data.length > 0 ? false : true` (data KHÁC RỖNG = phải cập nhật). Quy về boolean kiểu v1 cho
    _profile_needs_update; dạng khác giữ nguyên (-> 'không biết' nếu không phải bool)."""
    if isinstance(v, (list, str)):
        return len(v) == 0
    return v

def todo_items(open_feedback, update_profile, applications):
    """THUẦN: các việc sinh viên phải TỰ làm — list chuỗi, rỗng = không có việc gì.
      open_feedback  : CheckOpenFeedBack.data thô (None = không lấy được)
      update_profile : CheckUpdateProfile.data thô (None = không lấy được)
      applications   : các dòng GetApplication (None = không lấy được)"""
    items = []
    if _feedback_open(open_feedback):
        # App 2.0.5: "You need to do a teaching survey. Please access https://fap.fpt.edu.vn" + nút mở đúng trang đó
        items.append(t("📝 Đang mở đợt feedback giảng dạy — làm tại fap.fpt.edu.vn (app myFAP cũng dẫn tới đó).",
                       "📝 A teaching-feedback round is open — complete it at fap.fpt.edu.vn (where the myFAP app sends you)."))
    if _profile_needs_update(update_profile):
        items.append(t("👤 FAP yêu cầu cập nhật hồ sơ sinh viên — cập nhật tại fap.fpt.edu.vn (app myFAP cũng dẫn tới đó).",
                       "👤 FAP asks you to update your student profile — do it at fap.fpt.edu.vn (where the myFAP app sends you)."))
    for r in applications or []:
        if _app_code(r) == "3":                           # '3' = Đang chờ thanh toán (getStatusConfig 2.0.5)
            name = fmt.unescape(r.get("name")) or t("(đơn)", "(application)")
            date = fmt.unescape(r.get("createDate"))
            name += f" ({date})" if date else ""
            items.append(t(f"💳 Đơn chờ thanh toán: {name} — xem & thanh toán qua app myFAP / fap.fpt.edu.vn.",
                           f"💳 Application awaiting payment: {name} — check and pay via the myFAP app / fap.fpt.edu.vn."))
    return items

def todo_block(open_feedback, update_profile, applications, err=None):
    """THUẦN: khối "Việc cần làm · To-do" hoàn chỉnh. Nguồn nào KHÔNG BIẾT (lỗi) thì ghi chú rõ — KHÔNG BAO GIỜ
    nói "không có việc gì" khi chẳng kiểm tra được gì. `err` = lý do lỗi đầu tiên (vd token hết hạn)."""
    items = todo_items(open_feedback, update_profile, applications)
    checks = [(t("feedback", "feedback"), _feedback_open(open_feedback) is not None),
              (t("hồ sơ", "profile"), _profile_needs_update(update_profile) is not None),
              (t("đơn từ", "applications"), applications is not None)]
    unknown = [lbl for lbl, known in checks if not known]
    note = (t("❔ Chưa kiểm tra được: ", "❔ Couldn't check: ") + ", ".join(unknown)) if unknown else ""
    if not items:
        if len(unknown) == len(checks):
            head = t("📌 Việc cần làm: ❔ chưa kiểm tra được (mạng/token?).", "📌 To-do: ❔ couldn't check (network/token?).")
            return "\n".join(x for x in (head, err) if x)
        return "\n".join(x for x in (t("📌 Việc cần làm: ✅ không có việc gì.", "📌 To-do: ✅ nothing to do."), note) if x)
    lines = [fmt.header("📌", t("Việc cần làm", "To-do"), str(len(items)))] + items
    if note:
        lines.append(note)
    lines.append(t("ℹ️ fap-cli chỉ ĐỌC — tự làm các việc trên qua kênh chính thức (app myFAP / fap.fpt.edu.vn).",
                   "ℹ️ fap-cli is read-only — do these yourself via the official channels (myFAP app / fap.fpt.edu.vn)."))
    return "\n".join(lines)

def todo_fetch(token, campus, roll):
    """Dữ liệu cho khối to-do: 3 GET (CheckOpenFeedBack · CheckUpdateProfile · GetApplication), MỖI cái CÔ LẬP
    lỗi -> None (không biết), không bao giờ làm sập khối.
    Trả (open_feedback, update_profile, applications, err) — err = lý do lỗi ĐẦU TIÊN."""
    errs = []
    def _try(fn):
        try:
            return fn()
        except (Exception, SystemExit) as e:      # noqa: BLE001 — 1 nguồn hỏng chỉ thành "không biết"
            errs.append(str(e) or type(e).__name__)
            return None
    fb = _try(lambda: _fetch_ok("CheckOpenFeedBack", token, campus, roll))
    up = _try(lambda: _fetch_ok("CheckUpdateProfile", token, campus, roll))
    apps = _try(lambda: fetch_applications_checked(token, campus, roll))
    data = lambda res: res[1] if res and res[0] else None
    up_data = data(up)
    if up_data is not None and apiv2.api_version() == "v2":
        up_data = _profile_flag_v2(up_data)
    return data(fb), up_data, apps, (errs[0] if errs else None)

def todo_text(token, campus, roll):
    return todo_block(*todo_fetch(token, campus, roll))

def todo():
    token, campus, roll = creds()
    print(todo_text(token, campus, roll))

# ---------- DANH SÁCH CAMPUS (giúp người MỚI biết campusCode TRƯỚC khi login) ----------
def campuses_text():
    """GetAllActiveCampus — KHÔNG cần token/đăng nhập. Trả bảng campusCode + tên (chọn campus trước `fap login`)."""
    http, data = call("GetAllActiveCampus", [], "", "", checksum_value=False)   # endpoint công khai, không checksum
    rows = as_list(data)
    if not rows:
        return t("Không lấy được danh sách campus (kiểm tra mạng).", "Couldn't fetch campus list (check network).")
    return t(f"== Campus đang hoạt động ({len(rows)}) ==", f"== Active campuses ({len(rows)}) ==") + "\n" + fmt.table(rows)

def campuses():
    print(campuses_text())

# ---------- LỊCH THI (có bản trả-text cho bot/notify) ----------
# GetScheduleExam trả mỗi môn 1 dict. Dữ liệu THẬT (đã xác nhận): subjectCode + examDate ('m/d/Y') +
# examTime ('HH:MM') + examRoom; có thể kèm examType (PE/FE/2ndFE…) / examForm / groupName. Tên field
# đổi theo campus/kỳ -> DÒ ĐA BIẾN-THỂ (không phân biệt hoa/thường) như courses.py, đừng cứng 1 tên.
# Thẻ lịch thi của app myFAP 2.0.5 đọc: realSubject (Môn thi) · date · time · roomNo · kythi (Kiểu) · note.
# Danh sách này dùng CHUNG cho `fap exams`, exam-countdown và .ics — sửa 1 chỗ, 3 nơi cùng đúng.
_EX_SUBJ  = ("subjectcode", "subject", "examsubject", "realsubject", "subjectname")
_EX_ROOM  = ("examroom", "room", "roomno", "phongthi", "examroomname")
_EX_TYPE  = ("examtype", "type", "publicexamtype", "kythi")
_EX_FORM  = ("examform", "form", "method", "examformat")

def _exam_get(r, keys):
    """Giá trị đầu tiên KHÁC RỖNG trong các key ứng viên (không phân biệt hoa/thường). '' nếu không có."""
    if not isinstance(r, dict):
        return ""
    low = {str(k).lower(): v for k, v in r.items()}
    for k in keys:
        v = low.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""

def _exam_line(r):
    """1 dòng lịch thi ĐÃ ĐỊNH DẠNG (thay cho việc đổ thô mọi value):
    '• MÃ — Tên môn — DD/MM/YYYY HH:MM  📍 phòng  · type · form'. Trả (dòng, start_dt|None) để sort."""
    subj = _exam_get(r, _EX_SUBJ) or "?"
    dt = _exam_dt(r) if isinstance(r, dict) else None       # parse ngày/giờ generic (m/d/Y ưu tiên)
    if dt:
        when = dt[0].strftime("%d/%m/%Y %H:%M")
    else:                                                    # không parse được -> hiện thô cái đang có
        when = " ".join(x for x in (_exam_get(r, ("examdate", "date")),
                                    _exam_get(r, ("examtime", "time"))) if x)
    room = _exam_get(r, _EX_ROOM)
    tags = [b for b in (_exam_get(r, _EX_TYPE), _exam_get(r, _EX_FORM)) if b]
    line = f"• {subjects.label(subj)}"
    if when:
        line += f" — {when}"
    if room:
        line += f"  📍 {room}"
    if tags:
        line += "  · " + " · ".join(tags)
    return line, (dt[0] if dt else None)

def exams_text(token, campus, roll, sem):
    http, data = call("GetScheduleExam",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem), ("Authen", token)], roll, campus)
    check_auth(http, data)        # token hết hạn -> raise rõ, KHÔNG báo nhầm "chưa có lịch thi"
    rows = [r for r in as_list(data) if isinstance(r, dict)]
    if not rows:
        return t(f"📝 Chưa có lịch thi kỳ {sem} (sẽ hiện khi trường xếp lịch).",
                 f"📝 No exam schedule for {sem} yet (appears once scheduled).")
    subjects.load()                                          # tên môn từ cache (nếu đã `fap subjects`)
    rendered = [_exam_line(r) for r in rows]
    rendered.sort(key=lambda x: x[1] or datetime.datetime.max)   # sớm nhất trước; không-parse-được xuống cuối
    lines = [fmt.header("📝", t(f"Lịch thi {sem}", f"Exam schedule {sem}"),
                        t(f"{len(rows)} môn", f"{len(rows)} exams"))]
    lines += [ln for ln, _ in rendered]
    return "\n".join(lines)

def exams():
    token, campus, roll = creds()
    print(exams_text(token, campus, roll, current_semester(token, campus, roll)))

# ---------- TIN TỨC ----------
def fetch_news(token, campus, roll, keyword=None, type="1"):
    """GetTop10News (mặc định) HOẶC SearchNews khi có `keyword`. checksum_auth(type, campus) (như GetTop10News).
    Trả list dict đã decode entity. Rỗng nếu lỗi/không có.
    type mặc định '1' — bảng tin chung của trường (đã probe live: type '0' thường RỖNG với nhiều campus)."""
    if keyword:
        http, data = call("SearchNews",
            [("campusCode", campus), ("Authen", token), ("keysearch", keyword), ("type", str(type))],
            roll, campus, checksum_value=checksum_auth(str(type), campus))
    else:
        http, data = call("GetTop10News", [("campusCode", campus), ("Authen", token), ("type", str(type))],
                          roll, campus, checksum_value=checksum_auth(str(type), campus))
    check_auth(http, data)
    return [{k: fmt.unescape(v) if isinstance(v, str) else v for k, v in r.items()}
            for r in as_list(data) if isinstance(r, dict)]

def _news_get(n, keys):
    """Giá trị đầu tiên KHÁC RỖNG trong các khóa ứng viên — KHÔNG phân biệt hoa/thường (như _exam_get).
    Field tin của FAP đổi theo campus/kỳ: màn tin của app 2.0.5 đọc 'tittle'/'content'/'createDate', còn
    docs/03 ghi bộ khoá hoa 'Title'/'Contents'/'EntryDate'/'EntryBy' — so khớp chữ thường thì bắt được cả hai.
    Duyệt theo THỨ TỰ ưu tiên của `keys`; giá trị toàn khoảng trắng coi như rỗng (thử khoá kế tiếp)."""
    if not isinstance(n, dict):
        return ""
    for k in keys:
        want = k.lower()
        for key, v in n.items():               # không gộp thành dict chữ-thường: 'title' rỗng + 'Title' có
            if str(key).lower() == want and v is not None and str(v).strip():   # chữ thì vẫn lấy được
                return v
    return ""

def _html_snippet(raw, limit=180):
    """THUẦN: bóc thẻ HTML + decode entity + gộp khoảng trắng -> đoạn trích 1 dòng (≤limit). Rỗng -> ''."""
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", str(raw))               # bỏ thẻ
    txt = re.sub(r"\s+", " ", fmt.unescape(txt)).strip()  # &nbsp;/&amp;… + gộp trắng (kể cả \xa0)
    return (txt[:limit].rstrip() + "…") if len(txt) > limit else txt

# Khoá ứng viên của 1 mục tin (so khớp KHÔNG phân biệt hoa/thường qua _news_get).
_NEWS_TITLE = ("tittle", "title", "subject")                    # 'tittle' = typo GỐC của FAP, app đọc đúng tên này
_NEWS_DATE  = ("createDate", "editDate", "entryDate", "date")   # entryDate cũng bắt 'EntryDate'
_NEWS_BODY  = ("content", "contents", "body", "description")    # 'Contents' (có "s") theo docs/03
_NEWS_BY    = ("entryBy", "createBy", "author")                 # nơi đăng — có thì hiện cạnh ngày

def _news_line(n):
    """1 mục tin GỌN: tiêu đề + ngày (· nơi đăng) + trích ngắn. Field FAP thật: 'tittle' (typo của FAP),
    'content', 'createDate'; biến thể hoa 'Title'/'Contents'/'EntryDate'/'EntryBy' cũng đọc được."""
    title = fmt.unescape(_news_get(n, _NEWS_TITLE)) or t("(không tiêu đề)", "(no title)")
    raw_date = _news_get(n, _NEWS_DATE)
    date = fmt.fmt_date(raw_date) if raw_date else ""
    by = fmt.unescape(_news_get(n, _NEWS_BY))
    snippet = _html_snippet(_news_get(n, _NEWS_BODY))
    line = f"• {title}"
    meta = " · ".join(x for x in (date, by) if x)
    if meta:
        line += f"\n   🗓 {meta}"
    if snippet:
        line += f"\n   {snippet}"
    return line

def news_text(token, campus, roll, keyword=None, type="1", limit=10):
    """Tin tức render SẠCH (tiêu đề + ngày + trích, MỚI NHẤT trước) — thay bảng thô đổ nguyên HTML."""
    rows = fetch_news(token, campus, roll, keyword, type)
    if not rows:
        return t(f"📰 Không có tin{' khớp ' + repr(keyword) if keyword else ''}.",
                 f"📰 No news{' matching ' + repr(keyword) if keyword else ''}.")
    rows = sorted(rows, key=lambda n: str(_news_get(n, _NEWS_DATE) or ""), reverse=True)[:limit]
    head = t(f"Tin tức · tìm {keyword!r}", f"News · search {keyword!r}") if keyword else t("Tin tức", "News")
    return "\n".join([fmt.header("📰", head, str(len(rows)))] + [_news_line(n) for n in rows])

def news(keyword=None, type="1"):
    token, campus, roll = creds()
    print(news_text(token, campus, roll, keyword, type))

# ---------- HỌC PHÍ / SỐ DƯ ----------
# Trang hoá đơn / thanh toán điện tử mà màn Học phí của app mở (nút `lb_fee_dng`, Linking.openURL ra trình
# duyệt). myFAP 2.0.5 hiện nút này cho MỌI campus — KHÔNG chỉ Đà Nẵng dù host là dng.fpt.edu.vn.
# fap-cli chỉ DỰNG link tại chỗ (không gọi, không tải) để người dùng tự mở.
INVOICE_URL = "https://dng.fpt.edu.vn/Invoice?StudentId="

def invoice_url(roll):
    """THUẦN: link trang hoá đơn điện tử của MSSV `roll` ('' nếu thiếu MSSV).
    ⚠️ Link chứa MSSV -> CHỈ in ở `fap fees` (terminal của chính bạn), KHÔNG đưa vào bot/notify/web."""
    r = str(roll or "").strip()
    return INVOICE_URL + urllib.parse.quote(r, safe="") if r else ""

def fee_details_text(http, fee):
    """THUẦN: phần "chi tiết học phí" từ phản hồi GeFeeByRoll (http, data) — xét HTTP status TRƯỚC.
    Với nhiều tài khoản FAP trả HTTP 404 + JSON {'Message': …} (không có envelope code/data): đó là endpoint
    KHÔNG dùng được cho tài khoản này, không phải "chưa có học phí" -> nói đúng như vậy."""
    if http == 404:
        return t("(Mục chi tiết học phí không dùng được với tài khoản của bạn — FAP trả 404 cho GeFeeByRoll. "
                 "Số dư ở trên lấy từ endpoint khác, không bị ảnh hưởng.)",
                 "(Fee details aren't available for your account — FAP returns 404 for GeFeeByRoll. "
                 "The balance above comes from a different endpoint and isn't affected.)")
    if http is None:                                       # lỗi mạng: `fee` là thông báo ĐÃ che token của call()
        return t(f"(Không lấy được chi tiết học phí: {fee})", f"(Couldn't fetch fee details: {fee})")
    if http != 200:
        return t(f"(Không lấy được chi tiết học phí — FAP trả HTTP {http}.)",
                 f"(Couldn't fetch fee details — FAP returned HTTP {http}.)")
    rows = as_list(fee)
    if rows:
        return t("Chi tiết học phí:", "Fee details:") + "\n" + fmt.table(rows)
    return t("(Chưa có chi tiết học phí cho tài khoản này.)", "(No fee details for this account yet.)")

def invoice_text(roll):
    """THUẦN: dòng link hoá đơn điện tử có nhãn trung tính 2 thứ tiếng ('' nếu thiếu MSSV)."""
    url = invoice_url(roll)
    if not url:
        return ""
    return t(f"🧾 Hoá đơn / thanh toán điện tử (mở bằng trình duyệt): {url}\n"
             "   (link có MSSV của bạn — đừng dán vào nhóm chat công khai)",
             f"🧾 E-invoice / online payment page (open in a browser): {url}\n"
             "   (the link contains your roll number — don't post it in public chats)")

def fees():
    token, campus, roll = creds()
    http, bal = call("GetBalance", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, bal)         # nếu không, in nguyên envelope lỗi 201 thành "số dư"
    print(t(f"💰 Số dư tài khoản: {unwrap(bal)}", f"💰 Account balance: {unwrap(bal)}"))
    http, fee = call("GeFeeByRoll", [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    if http != 404:               # 404 = endpoint không dùng được cho tài khoản này (xử lý ở fee_details_text),
        check_auth(http, fee)     #       KHÔNG phải lỗi xác thực -> đừng để check_auth đoán
    print(fee_details_text(http, fee))
    line = invoice_text(roll)
    if line:
        print(line)

# ---------- THÔNG BÁO CÁ NHÂN (GetNotificationByRoll) ----------
def fetch_notifications(token, campus, roll):
    http, data = call("GetNotificationByRoll",
        [("campusCode", campus), ("Authen", token), ("rollNumber", roll)], roll, campus)
    check_auth(http, data)
    return as_list(data)

_NOTIF_PREVIEW = 140      # ký tự trích nội dung dưới mỗi thông báo (đủ biết "chuyện gì" mà không dài tin)

# CHỈ bóc thẻ HTML THẬT (theo tên thẻ). `contents` thực tế là TEXT THUẦN (đo trên dump: 0/19 có '<'), nên
# regex kiểu `<[^>]+>` sẽ XOÁ NHẦM chữ thật: '<MSSV>_<HoTen>.pdf', 'điểm < 5 … ->', '<https://…>' — và vì
# [^>] khớp cả xuống dòng, có thể nuốt MẤT NHIỀU DÒNG. `[^<>]*` không cho một "thẻ" vắt qua dấu '<' khác.
_HTML_TAG = re.compile(r"(?i)</?(?:p|br|div|span|b|i|u|a|li|ul|ol|strong|em|font|table|thead|tbody|tr|td|th"
                       r"|h[1-6]|img|hr|sup|sub|small|center|blockquote|section|article)\b[^<>]*>")
_HTML_BREAK = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|tr|h[1-6]|section|article)\s*>")

def _notif_body(n):
    """THUẦN: nội dung thông báo dạng text GIỮ xuống dòng. Bóc thẻ HTML thật (nếu server gửi HTML), giải
    entity SAU khi bóc (nên '&lt;MSSV&gt;' ra '<MSSV>' và được GIỮ), gộp các dòng trống liền nhau."""
    raw = str(n.get("contents") or "")
    raw = fmt.unescape(_HTML_TAG.sub(" ", _HTML_BREAK.sub("\n", raw)))
    out, blank = [], False
    for line in raw.split("\n"):
        line = " ".join(line.split())
        if line:
            out.append(line); blank = False
        elif out and not blank:
            out.append(""); blank = True
    return "\n".join(out).strip()

def _preview(text, limit=_NOTIF_PREVIEW):
    """THUẦN: 1 dòng trích ≤limit. KHÔNG bóc thẻ lần 2 (text đã sạch). Nếu điểm cắt rơi GIỮA một URL thì lùi
    về trước URL đó — không để lại link cụt mà chat vẫn biến thành link bấm được (bấm vào là trang lỗi)."""
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    cut = s[:limit]
    sp = cut.rfind(" ")
    token = s[sp + 1:].split(" ", 1)[0]
    if "://" in token or token.lower().startswith("www."):
        cut = cut[:sp] if sp > 0 else ""
    cut = cut.rstrip()
    return (cut + "…") if cut else ""

def _notif_id(n):
    """Khoá ỔN ĐỊNH của 1 thông báo = `id` của server ('' nếu thiếu). KHÔNG dùng vị trí trong danh sách:
    vị trí đổi mỗi khi có thông báo mới, và Discord render '3. …' thành danh sách Markdown rồi TỰ ĐÁNH SỐ LẠI
    ⇒ 'notifications <n>' mở NHẦM cái khác. id: 2–3 chữ số trên dump thật, duy nhất."""
    v = n.get("id")
    return str(v).strip() if v is not None and str(v).strip() else ""

def _notif_meta(n):
    return " · ".join(x for x in (fmt.fmt_date(n.get("entryDate")) if n.get("entryDate") else "",
                                  fmt.unescape(n.get("entryBy"))) if x)

def _notif_line(n):
    """1 mục gọn: '#<id> · tiêu đề' · ngày · nơi gửi · 1 dòng trích. Dùng CHUNG cho /notifications và tin
    đẩy "thông báo MỚI" — cùng một số #id ở cả hai nơi, nên từ tin đẩy gõ '/notifications <id>' là mở đúng."""
    title = fmt.unescape(n.get("title")) or t("(không tiêu đề)", "(no title)")
    nid = _notif_id(n)
    meta = _notif_meta(n)
    line = (f"#{nid} · {title}" if nid else f"• {title}") + (f"\n   {meta}" if meta else "")
    snip = _preview(_notif_body(n))
    if snip and snip != title:                                # nội dung chỉ lặp tiêu đề -> khỏi in 2 lần
        line += f"\n   💬 {snip}"
    return line

def _notif_full(n):
    """Toàn văn MỘT thông báo."""
    title = fmt.unescape(n.get("title")) or t("(không tiêu đề)", "(no title)")
    nid, meta = _notif_id(n), _notif_meta(n)
    body = _notif_body(n) or t("(không có nội dung)", "(no content)")
    return "\n".join([fmt.header("🔔", t(f"Thông báo #{nid}", f"Notification #{nid}")), title]
                     + ([f"🗓 {meta}"] if meta else []) + ["", body])

def notifications_text(token, campus, roll, limit=10, arg=None):
    """Danh sách thông báo mới nhất (kèm trích nội dung), mỗi mục mang số #id ỔN ĐỊNH. `arg`:
       số (có/không '#')  -> TOÀN VĂN thông báo có id đó
       từ khoá            -> chỉ các thông báo có từ khoá trong tiêu đề/nội dung."""
    rows = fetch_notifications(token, campus, roll)
    if not rows:
        return t("🔔 Không có thông báo.", "🔔 No notifications.")
    rows = sorted((n for n in rows if isinstance(n, dict)),
                  key=lambda n: str(n.get("entryDate") or ""), reverse=True)
    a = str(arg or "").strip()
    key = a.lstrip("#").strip()
    if key and key.isascii() and key.isdecimal():            # isdigit() nhận cả '²' rồi int() nổ
        hit = next((n for n in rows if _notif_id(n) == key.lstrip("0") or _notif_id(n) == key), None)
        if hit is None:
            return t(f"🔔 Không có thông báo #{key} (xem số #id trong /notifications).",
                     f"🔔 No notification #{key} (see the #id numbers in /notifications).")
        return _notif_full(hit)
    if a:
        kw = a.casefold()
        rows = [n for n in rows if kw in (fmt.unescape(n.get("title")) + "\n" + _notif_body(n)).casefold()]
        if not rows:
            return t(f"🔔 Không có thông báo nào khớp {a!r}.", f"🔔 No notifications matching {a!r}.")
    shown = rows[:limit]
    head = t(f"Thông báo · tìm {a!r}", f"Notifications · search {a!r}") if a else t("Thông báo mới nhất", "Latest notifications")
    lines = [fmt.header("🔔", head, str(len(shown)))] + [_notif_line(n) for n in shown]
    lines.append("\n" + t("👉 Toàn văn: /notifications <số #> · lọc: /notifications <từ khoá>",
                          "👉 Full text: /notifications <# number> · filter: /notifications <keyword>"))
    return "\n".join(lines)

def notifications(arg=None):
    token, campus, roll = creds()
    print(notifications_text(token, campus, roll, arg=arg))

# ---------- XUẤT LỊCH THI -> .ics (Calendar TỰ NHẮC trước 1 ngày) ----------
def _exam_rows(token, campus, roll, sem):
    http, data = call("GetScheduleExam",
        [("campusCode", campus), ("rollNumber", roll), ("Semester", sem), ("Authen", token)], roll, campus)
    check_auth(http, data)
    return as_list(data)

def _exam_dt(r):
    """(start, end) từ 1 dòng lịch thi — parse generic ngày + giờ. None nếu không đọc được ngày."""
    import re, datetime
    dv = next((r[k] for k in r if str(k).lower() in ("examdate", "date", "ngaythi", "examday") and r[k]), None)
    if not dv:
        return None
    ds = str(dv).split("T")[0].split(" ")[0]
    day = None
    for f in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try: day = datetime.datetime.strptime(ds, f).date(); break
        except ValueError: continue
    if not day:
        return None
    def _clock(s):
        # chấp nhận '07h30' (FAP dùng 'h') và '07:30'; lấy giờ ĐẦU nếu là khoảng '07h30-08h50'
        m = re.search(r"(\d{1,2})\s*[h:]\s*(\d{2})", str(s or ""))
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            return int(m.group(1)), int(m.group(2))
        return None
    hh, mm = 7, 0
    tv = next((r[k] for k in r if str(k).lower() in ("examtime", "time", "giothi", "starttime") and r[k]), None)
    for src in (tv, dv):                 # ưu tiên field GIỜ riêng (vd '07h30-08h50'), rồi giờ nhúng trong field ngày
        c = _clock(src)
        if c and c != (0, 0):            # bỏ '00:00' GIẢ từ field ngày dạng '...T00:00:00'
            hh, mm = c; break
    s = datetime.datetime(day.year, day.month, day.day, hh, mm)
    return s, s + datetime.timedelta(hours=2)

# ---------- ĐẾM NGƯỢC LỊCH THI (exam-countdown) ----------
def exam_countdown(rows, now):
    """THUẦN: [(days, start_dt, subjectCode, room)] cho kỳ thi SẮP tới (bỏ đã qua), sớm nhất trước.
    `now` truyền vào (datetime naive, giờ VN) → test offline được. Dùng lại `_exam_dt` (parse generic) và
    CÙNG getter + danh sách khoá với `fap exams` (_exam_get/_EX_SUBJ/_EX_ROOM, không phân biệt hoa/thường):
    trước đây đọc cứng 'subjectCode'/'examRoom' nên hàng 'SubjectCode'/'examSubject' ra '?' dù `fap exams` đúng."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):                    # as_list có thể lẫn phần tử lạ -> bỏ, đừng nổ
            continue
        dt = _exam_dt(r)
        if not dt:
            continue
        days = (dt[0].date() - now.date()).days
        if days < 0:                                   # đã thi xong → bỏ
            continue
        out.append((days, dt[0], _exam_get(r, _EX_SUBJ) or "?", _exam_get(r, _EX_ROOM)))
    out.sort(key=lambda x: x[1])
    return out

def countdown_text(token, campus, roll, sem, now=None):
    now = now or _vn_now().replace(tzinfo=None)
    subjects.load()
    items = exam_countdown(_exam_rows(token, campus, roll, sem), now)
    if not items:
        return t("⏳ Chưa có lịch thi sắp tới.", "⏳ No upcoming exams.")
    out = [fmt.header("⏳", t(f"Đếm ngược thi · {sem}", f"Exam countdown · {sem}"),
                      t(f"{len(items)} môn", f"{len(items)} exams"))]
    for days, start, subj, room in items:
        if days == 0:   tag = t("🔴 HÔM NAY", "🔴 TODAY")
        elif days == 1: tag = t("🟠 NGÀY MAI", "🟠 TOMORROW")
        elif days <= 3: tag = t(f"🟡 còn {days} ngày", f"🟡 in {days} days")
        else:           tag = t(f"⚪ còn {days} ngày", f"⚪ in {days} days")
        line = f"• {subjects.label(subj)} — {start.strftime('%d/%m %H:%M')}  {tag}"
        if room:
            line += f"  📍 {room}"
        out.append(line)
    return "\n".join(out)

def exam_countdown_cmd():
    token, campus, roll = creds()
    print(countdown_text(token, campus, roll, current_semester(token, campus, roll)))

def build_exam_ics(rows):
    """THUẦN: rows GetScheduleExam -> (ics_str, n_events, n_skipped). Mỗi môn kèm VALARM -P1D (nhắc trước 1 ngày)."""
    from .schedule import _esc, _fmt, TZID
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FAP//Exams//VI", "CALSCALE:GREGORIAN"]
    n = skipped = 0
    for r in rows:
        p = _exam_dt(r) if isinstance(r, dict) else None
        if not p:
            skipped += 1; continue
        s, e = p
        subj = _exam_get(r, _EX_SUBJ) or "Thi"
        room = _exam_get(r, _EX_ROOM)
        desc = " • ".join(b for b in (f"Môn {subj}", f"Phòng {room}" if room else "",
                                      _exam_get(r, _EX_TYPE), _exam_get(r, _EX_FORM)) if b)
        lines += ["BEGIN:VEVENT", f"UID:exam-{subj}-{_fmt(s)}-{n}@fap", f"SUMMARY:{_esc('[Thi] ' + str(subj))}",
                  f"DTSTART;TZID={TZID}:{_fmt(s)}", f"DTEND;TZID={TZID}:{_fmt(e)}",
                  f"LOCATION:{_esc(room)}", f"DESCRIPTION:{_esc(desc)}",
                  "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:Nhac thi (truoc 1 ngay)", "END:VALARM",
                  "END:VEVENT"]
        n += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", n, skipped

def exams_ics():
    """output/lichthi.ics — import vào Calendar để được nhắc tự động trước giờ thi.
    Field GetScheduleExam đã xác nhận từ dữ liệu thật (subjectCode/examDate/examTime/examRoom) nhưng parse
    ngày/giờ vẫn generic (m/d/Y ưu tiên) + dò đa biến-thể -> dòng nào không đọc được ngày thì bỏ qua."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    rows = _exam_rows(token, campus, roll, sem)
    if not rows:
        print(t(f"📝 Chưa có lịch thi kỳ {sem} để xuất.", f"📝 No exam schedule for {sem} to export.")); return
    ics, n, skipped = build_exam_ics(rows)
    if not n:
        print(t(f"⚠️ Không đọc được ngày/giờ của {skipped} dòng lịch thi — gửi `fap exams` cho tôi để chỉnh parser.",
                f"⚠️ Couldn't parse date/time for {skipped} exam rows — share `fap exams` output to tune.")); return
    out = paths.out_dir()                         # output/ hoặc output/profiles/<tên>/ (xem core/paths.py)
    os.makedirs(out, exist_ok=True)               # thư mục có thể chưa tồn tại (checkout sạch / chưa login)
    path = os.path.join(out, "lichthi.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    tail = (f" (bỏ {skipped} dòng)" if skipped else "")
    print(t(f"✓ Ghi {n} môn thi -> output/lichthi.ics{tail}", f"✓ Wrote {n} exams -> output/lichthi.ics{tail}"))
    print(t("  Import: Google Calendar → Settings → Import & Export.", "  Import via Google Calendar settings."))
