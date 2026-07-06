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

Chỉ xin quyền GHI SỰ KIỆN (calendar.events). Token Google lưu output/gcal_token.json — ĐỪNG commit.
"""
import os, sys
from ..core.api import creds, current_semester
from ..core.schedule import fetch_sessions, parse_session  # tái dùng parser ngày/giờ
from ..i18n import t
from .. import config, fmt

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRED_FILE  = os.path.join(ROOT, "credentials.json")
TOKEN_FILE = os.path.join(ROOT, "output", "gcal_token.json")

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
        creds_.refresh(Request()); _save(creds_); return creds_
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
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds_.to_json())
    try: os.chmod(TOKEN_FILE, 0o600)
    except Exception: pass

def _service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=_load_creds(False), cache_discovery=False)

def _events(sessions):
    for s in sessions:
        p = parse_session(s)
        if not p:
            continue
        start, end, _ = p
        subj, room = s.get("subjectCode", "Lớp"), s.get("roomNo", "")
        online = fmt.is_online(s)
        uid = f"fapc-{start.strftime('%Y%m%d')}-{subj}-{s.get('slot','')}@fap.fpt.edu.vn"
        yield {
            "iCalUID": uid,
            "summary": subj + (f" @ {room}" if room and not online else (" (Online)" if online else "")),
            "location": "Online" if online else room,
            "description": f"Môn {subj} • Lớp {s.get('groupName','')} • Slot {s.get('slot','')} • "
                           f"GV {s.get('lecturer','')} • Buổi {s.get('sessionNo','')}",
            "start": {"dateTime": start.isoformat(), "timeZone": config.TZID},
            "end":   {"dateTime": end.isoformat(),   "timeZone": config.TZID},
            "extendedProperties": {"private": {"fapc": "1"}},
        }

# ---------- DỌN event MỒ CÔI (prune) — CHỈ event fap-cli tạo, KHÔNG đụng lịch cá nhân ----------
def _current_uids(sessions):
    """THUẦN: tập iCalUID của lịch HIỆN TẠI (buổi còn hợp lệ)."""
    return {ev["iCalUID"] for ev in _events(sessions)}

def _list_fapc_events(svc, cal_id):
    """MỌI event do fap-cli tạo (lọc theo nhãn private fapc=1 → KHÔNG đụng event cá nhân), có phân trang."""
    out, page = [], None
    while True:
        resp = svc.events().list(calendarId=cal_id, privateExtendedProperty="fapc=1",
                                 singleEvents=True, showDeleted=False, maxResults=2500, pageToken=page).execute()
        out += resp.get("items", [])
        page = resp.get("nextPageToken")
        if not page:
            break
    return out

def _prune_plan(fapc_events, current_uids):
    """THUẦN: event fapc KHÔNG còn trong lịch hiện tại → [(id, iCalUID, summary)] cần XÓA (buổi hủy/dời)."""
    return [(ev.get("id"), ev.get("iCalUID", ""), ev.get("summary", ""))
            for ev in fapc_events if ev.get("iCalUID") and ev.get("iCalUID") not in current_uids]

def _prune(svc, sessions, yes=False, force=False):
    """Xóa event fap-cli MỒ CÔI. Dry-run mặc định (chỉ in); >30% thì TỪ CHỐI (phòng lấy lịch lỗi) trừ --force."""
    fapc = _list_fapc_events(svc, config.GCAL_CALENDAR_ID)
    plan = _prune_plan(fapc, _current_uids(sessions))
    if not plan:
        print(t("✓ Không có sự kiện mồ côi để dọn.", "✓ No orphan events to prune.")); return
    if fapc and len(plan) / len(fapc) > 0.30 and not force:
        print(t(f"⚠️ {len(plan)}/{len(fapc)} sự kiện (>30%) sẽ bị xóa — TỪ CHỐI (lấy lịch có thể lỗi). Ép: thêm --force.",
                f"⚠️ {len(plan)}/{len(fapc)} events (>30%) would be deleted — REFUSED (bad fetch?). Override: --force."))
        return
    print(t(f"{'Đang xóa' if yes else '[DRY-RUN] sẽ xóa'} {len(plan)} sự kiện mồ côi (chỉ event fap-cli):",
            f"{'Deleting' if yes else '[DRY-RUN] would delete'} {len(plan)} orphan events (fap-cli only):"))
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

def cmd_auth():
    _load_creds(interactive=True)
    print(t("✓ Đã xác thực Google -> output/gcal_token.json", "✓ Google authorized -> output/gcal_token.json"))

def cmd_sync(prune=False, yes=False, force=False):
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    sessions = fetch_sessions(token, campus, roll, sem)
    print(t(f"Lấy {len(sessions)} buổi (kỳ {sem}). Đang đẩy lên Calendar '{config.GCAL_CALENDAR_ID}'...",
            f"Fetched {len(sessions)} sessions ({sem}). Pushing to calendar '{config.GCAL_CALENDAR_ID}'..."))
    svc = _service()
    ok = fail = 0
    for ev in _events(sessions):
        try:
            svc.events().import_(calendarId=config.GCAL_CALENDAR_ID, body=ev).execute()  # upsert theo iCalUID
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 3: print("  lỗi 1 sự kiện:", str(e)[:120])
    print(t(f"✓ Đồng bộ {ok} sự kiện (lỗi {fail}). Chạy lại = cập nhật, không trùng.",
            f"✓ Synced {ok} events (failed {fail}). Re-run = update, no duplicates."))
    if prune:                                        # dọn event buổi-đã-hủy/dời (chỉ event fap-cli)
        _prune(svc, sessions, yes=yes, force=force)

def cmd_prune(yes=False, force=False):
    """Dọn RIÊNG (không đẩy lại): xóa event fap-cli không còn trong lịch FAP hiện tại."""
    token, campus, roll = creds()
    sem = current_semester(token, campus, roll)
    _prune(_service(), fetch_sessions(token, campus, roll, sem), yes=yes, force=force)

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "sync"
    flags = {"yes": "--yes" in args, "force": "--force" in args}
    if cmd == "auth":    cmd_auth()
    elif cmd == "prune": cmd_prune(**flags)
    else:                cmd_sync(prune="--prune" in args, **flags)

if __name__ == "__main__":
    main()
