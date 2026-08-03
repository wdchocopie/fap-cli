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
    fap calendar-auth     # đăng nhập Google 1 lần (mở trình duyệt) -> output/gcal_token.json
    fap calendar-sync     # đẩy/cập nhật lịch hiện tại lên Google Calendar

Chỉ xin quyền GHI SỰ KIỆN (calendar.events). Token Google lưu output/gcal_token.json
(FAP_PROFILE=alice -> output/profiles/alice/gcal_token.json) — ĐỪNG commit.

NHIỀU TÀI KHOẢN (multi-profile): mọi sự kiện fap-cli tạo đều mang DẤU CHỦ SỞ HỮU = mã sinh viên
(iCalUID + nhãn riêng `fapc_owner`). Nhờ vậy hai người dùng chung 1 Google Calendar KHÔNG bao giờ
dọn (prune) trúng sự kiện của nhau. Xem `_owner()` / `_uids_for()` bên dưới.
"""
import os, re, sys
from ..core.api import creds, current_semester
from ..core.schedule import fetch_sessions, parse_session  # tái dùng parser ngày/giờ
from ..core import paths
from ..i18n import t
from .. import config, fmt

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRED_FILE  = os.path.join(ROOT, "credentials.json")   # credential của ỨNG DỤNG (dùng chung mọi profile) → ở gốc repo
TOKEN_FILE = paths.out("gcal_token.json")             # token của NGƯỜI DÙNG → theo profile

def _load_creds(interactive=False):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise SystemExit(t(
            "Thiếu thư viện Google. Cài: pip install google-api-python-client google-auth-oauthlib",
            "Missing Google libs. Install: pip install google-api-python-client google-auth-oauthlib"))
    creds_ = None
    if os.path.exists(TOKEN_FILE):
        try: creds_ = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
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
        except RefreshError as e:                         # CHỈ token hết hạn/thu hồi (KHÁC lỗi mạng tạm thời → để propagate)
            if not interactive:                           # cron/calendar-sync: báo GỌN như path token FAP, đừng phun traceback
                raise SystemExit(t(f"Token Google không refresh được ({type(e).__name__}). Chạy: fap calendar-auth",
                                   f"Google token could not refresh ({type(e).__name__}). Run: fap calendar-auth"))
            # interactive (calendar-auth): rơi xuống login lại bên dưới
        else:
            _save(creds_); return creds_                  # refresh OK → lưu (ngoài try: lỗi _save không bị nhầm là lỗi refresh)
    if interactive:
        from google_auth_oauthlib.flow import InstalledAppFlow
        if not os.path.exists(CRED_FILE):
            raise SystemExit(t(
                f"Thiếu {CRED_FILE}. Tạo OAuth client 'Desktop app' trên Google Cloud (bật Calendar API), "
                "tải credentials.json về gốc repo.",
                f"Missing {CRED_FILE}. Create a 'Desktop app' OAuth client on Google Cloud (enable Calendar API), "
                "download credentials.json to the repo root."))
        flow = InstalledAppFlow.from_client_secrets_file(CRED_FILE, SCOPES)
        creds_ = flow.run_local_server(port=0)
        _save(creds_); return creds_
    raise SystemExit(t("Chưa xác thực Google. Chạy: fap calendar-auth",
                       "Not authorized. Run: fap calendar-auth"))

def _save(creds_):
    paths.ensure_dir(TOKEN_FILE)                           # thư mục profile có thể chưa tồn tại
    tmp = TOKEN_FILE + ".tmp"                              # ghi nguyên tử: tmp -> os.replace (khỏi cụt file lúc bị ngắt)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(creds_.to_json())
    os.replace(tmp, TOKEN_FILE)
    try: os.chmod(TOKEN_FILE, 0o600)
    except Exception: pass

def _service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=_load_creds(False), cache_discovery=False)

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

def _prune(svc, sessions, owner, yes=False, force=False):
    """Xóa event fap-cli MỒ CÔI **của chính mã SV này**. Dry-run mặc định (chỉ in);
    >30% thì TỪ CHỐI (phòng lấy lịch lỗi) trừ --force."""
    claim_legacy = not paths.profile()                     # chỉ profile MẶC ĐỊNH mới được nhận lịch cũ chưa gắn dấu
    fapc = _list_fapc_events(svc, config.GCAL_CALENDAR_ID, owner, claim_legacy)
    adopt = {ev.get("iCalUID", "") for ev in fapc}
    plan = _prune_plan(fapc, _current_uids(sessions, owner, adopt))
    if not plan:
        print(t("✓ Không có sự kiện mồ côi để dọn.", "✓ No orphan events to prune.")); return
    if fapc and len(plan) / len(fapc) > 0.30 and not force:
        print(t(f"⚠️ {len(plan)}/{len(fapc)} sự kiện (>30%) sẽ bị xóa — TỪ CHỐI (lấy lịch có thể lỗi). Ép: thêm --force.",
                f"⚠️ {len(plan)}/{len(fapc)} events (>30%) would be deleted — REFUSED (bad fetch?). Override: --force."))
        return
    print(t(f"{'Đang xóa' if yes else '[DRY-RUN] sẽ xóa'} {len(plan)} sự kiện mồ côi (chỉ event fap-cli của {owner}):",
            f"{'Deleting' if yes else '[DRY-RUN] would delete'} {len(plan)} orphan events (fap-cli, owner {owner} only):"))
    for _id, _uid, summ in plan[:20]:
        print(f"   - {summ}")
    if len(plan) > 20:
        print(f"   … +{len(plan) - 20}")
    if not yes:
        print(t("→ Thêm --yes để xóa thật.", "→ Add --yes to actually delete.")); return
    deleted = 0
    for _id, _uid, summ in plan:
        try:
            svc.events().delete(calendarId=config.GCAL_CALENDAR_ID, eventId=_id).execute(); deleted += 1
        except Exception as e:                       # noqa: BLE001 — 1 event lỗi không dừng cả mẻ
            print("  lỗi xóa · delete error:", str(e)[:100])
    print(t(f"✓ Đã xóa {deleted} sự kiện mồ côi.", f"✓ Deleted {deleted} orphan events."))

def _adopt_set(svc, owner):
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
                _list_fapc_events(svc, config.GCAL_CALENDAR_ID, owner, claim_legacy=True)}
    except Exception as e:                                # noqa: BLE001 — mọi lỗi API đều dẫn tới cùng 1 kết luận
        raise SystemExit(t(
            f"Không đọc được sự kiện sẵn có trên Calendar ({str(e)[:120]}). DỪNG để tránh nhân đôi lịch.",
            f"Could not read existing calendar events ({str(e)[:120]}). STOPPING to avoid duplicating the calendar."))

def cmd_auth():
    _load_creds(interactive=True)
    print(t(f"✓ Đã xác thực Google -> {TOKEN_FILE}", f"✓ Google authorized -> {TOKEN_FILE}"))

def cmd_sync(prune=False, yes=False, force=False):
    token, campus, roll = creds()
    owner = _owner(roll)
    sem = current_semester(token, campus, roll)
    sessions = fetch_sessions(token, campus, roll, sem)
    print(t(f"Lấy {len(sessions)} buổi (kỳ {sem}). Đang đẩy lên Calendar '{config.GCAL_CALENDAR_ID}'"
            f" (chủ sở hữu: {owner}){paths.label()}...",
            f"Fetched {len(sessions)} sessions ({sem}). Pushing to calendar '{config.GCAL_CALENDAR_ID}'"
            f" (owner: {owner}){paths.label()}..."))
    svc = _service()
    adopt = _adopt_set(svc, owner)                   # "nhận nuôi" lịch đã có: giữ nguyên uid cũ, chỉ gắn thêm dấu chủ sở hữu
    ok = fail = 0
    for ev in _events(sessions, owner, adopt):
        try:
            svc.events().import_(calendarId=config.GCAL_CALENDAR_ID, body=ev).execute()  # upsert theo iCalUID
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 3: print("  lỗi 1 sự kiện:", str(e)[:120])
    print(t(f"✓ Đồng bộ {ok} sự kiện (lỗi {fail}). Chạy lại = cập nhật, không trùng.",
            f"✓ Synced {ok} events (failed {fail}). Re-run = update, no duplicates."))
    if prune:                                        # dọn event buổi-đã-hủy/dời (chỉ event fap-cli của tôi)
        _prune(svc, sessions, owner, yes=yes, force=force)

def cmd_prune(yes=False, force=False):
    """Dọn RIÊNG (không đẩy lại): xóa event fap-cli CỦA MÃ SV NÀY không còn trong lịch FAP hiện tại."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    _prune(_service(), fetch_sessions(token, campus, roll, sem), _owner(roll), yes=yes, force=force)

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "sync"
    flags = {"yes": "--yes" in args, "force": "--force" in args}
    if cmd == "auth":    cmd_auth()
    elif cmd == "prune": cmd_prune(**flags)
    else:                cmd_sync(prune="--prune" in args, **flags)

if __name__ == "__main__":
    main()
