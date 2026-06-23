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

def cmd_auth():
    _load_creds(interactive=True)
    print(t("✓ Đã xác thực Google -> output/gcal_token.json", "✓ Google authorized -> output/gcal_token.json"))

def cmd_sync():
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

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    {"auth": cmd_auth, "sync": cmd_sync}.get(cmd, cmd_sync)()

if __name__ == "__main__":
    main()
