#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli.py — điểm vào lệnh `fap` (gói fapc). Chạy: `fap <command>` hoặc `python -m fapc <command>`."""
import os, sys

# In tiếng Việt/emoji không lỗi trên console Windows (cp1252) — kể cả nhánh help/doctor
# (không import api.py). Phải đặt ở đây vì `fap` (không tham số) in HELP ngay, chưa import gì khác.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HELP = """fap <command>   ·   fap-cli

  Đăng nhập / Login (OAuth FE Identity):
    campuses               liệt kê campusCode (trước khi login) · list campus codes (no login)
    login                  đăng nhập Google 1 lần · one-time Google login
    refresh                làm mới token headless · refresh token headless
    exchange "<url>"       đổi URL redirect -> token · exchange redirect URL
    fap [campus]           đổi access_token đã lưu -> token FAP (khi login lỗi) · re-exchange saved token
    whoami                 xem token đã lưu · show saved token

  Tổng quan / Overview:
    status | dashboard     hôm nay + điểm + điểm danh · today + grades + attendance
    all                    MỌI thứ trong 1 lần · everything at once
    weekly                 tổng kết tuần: lịch + điểm danh + điểm (gửi kênh) · weekly recap → channels
    week [next|prev|N]     lịch tuần (lọc từ kỳ) · weekly schedule
    week-exact [week year] lịch tuần lấy thẳng server (chuẩn tuần nghỉ lễ) · weekly straight from server

  Dữ liệu / Data:
    extract                kéo toàn bộ -> output/ · pull everything
    ics                    xuất output/lichhoc.ics · export .ics
    grades | grades-detail điểm | điểm thành phần (+ "cần gì để qua") · grades | component grades (+ pass-projection)
    subjects               tải/cache danh mục môn → hiện TÊN + tín chỉ ở mọi nơi · cache subject names + credits
    attendance | banrisk   điểm danh | nguy cơ cấm thi · attendance | exam-ban risk
    transcript | gpa       bảng điểm tích lũy | GPA tích lũy (tín chỉ) · transcript | cumulative GPA
    whatif [target]        mô phỏng GPA · GPA what-if
    exams | exams-ics      lịch thi | xuất lịch thi ra .ics (Calendar tự nhắc) · exams | exams→.ics
    news | fees | notifications   tin tức | học phí | thông báo trường · news | fees | notifications
    profile | applications hồ sơ SV | đơn từ + trạng thái xử lý · student profile | applications

  Giao diện / UI:
    web [port]             dashboard web cục bộ (stdlib, 0 dep) · local web dashboard

  Đẩy / Push:
    calendar-auth          xác thực Google Calendar 1 lần · authorize Google Calendar
    calendar-sync          đồng bộ lịch lên Google Calendar · sync to Google Calendar
    notify [test|today|tomorrow|weekly|attendance|banrisk|grades|grades-detail|status|whatif|exams|gpa|notifications|all]   gửi lên kênh · push
    watch-attendance [loop [phút]] [--absent-only]   báo khi VỪA điểm danh; --absent-only = chỉ báo vắng/muộn
    watch-grades [loop [phút]]   báo khi có ĐIỂM MỚI (thành phần/tổng kết) · ping on new marks

  Bot tương tác / Interactive bots (chạy nền · long-running):
    telegram-bot           bot Telegram trả lời lệnh · interactive Telegram bot
    discord-bot            bot Discord trả lời lệnh · interactive Discord bot (cần · needs [bot])

    doctor                 tự kiểm tra môi trường · self-check
    selftest               chạy toàn bộ test offline (kiểm tool chạy đúng) · run offline test suites
"""

def selftest():
    """Chạy 2 bộ test OFFLINE (test_logic + integration_offline) — kiểm tool còn chạy đúng trên máy này.
    Không gọi mạng, không cần token. Trả 0 nếu tất cả pass."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rc = ran = 0
    for f in ("tests/test_logic.py", "tests/integration_offline.py"):
        path = os.path.join(root, f)
        if not os.path.exists(path):
            print(f"  — {f}: (không thấy)"); continue
        ran += 1
        print(f"▶ {f}")
        rc |= subprocess.run([sys.executable, path], cwd=root).returncode
    if ran == 0:        # cài qua wheel -> tests/ không đi kèm: KHÔNG báo PASS giả khi chẳng chạy gì
        print("\n⚠️ selftest: không tìm thấy bộ test nào (tests/ không đi kèm bản cài qua pip — chạy từ gốc repo).")
        return 1
    print("\n✅ selftest PASS — mọi thứ chạy đúng." if rc == 0 else "\n❌ selftest FAIL — xem dòng FAIL ở trên.")
    return rc

def doctor():
    from .. import config
    from ..core.api import TOKEN_JSON
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("Python      :", sys.version.split()[0])
    print("token.json  :", "✓" if os.path.exists(TOKEN_JSON) else "✗ (chạy: fap login)")
    print(".env        :", "✓" if os.path.exists(os.path.join(root, ".env")) else "—")
    try: import requests; print("requests    : ✓")  # noqa: F401
    except ImportError: print("requests    : ✗ (pip install -r requirements.txt)")
    try: import googleapiclient; print("google libs : ✓")  # noqa: F401
    except ImportError: print("google libs : — (chỉ cần cho calendar-sync)")
    print("kênh notify :", ", ".join(filter(None, [
        "Telegram" if config.TELEGRAM_TOKEN else "", "Discord" if config.DISCORD_WEBHOOK_URL else ""])) or "—")

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    if   cmd == "campuses":       from ..core.extras import campuses; campuses()
    elif cmd == "login":          from ..core.auth import cmd_login; cmd_login()
    elif cmd == "refresh":        from ..core.auth import refresh_tokens; refresh_tokens()
    elif cmd == "exchange":       from ..core.auth import exchange_code; exchange_code(rest[0] if rest else "")
    elif cmd == "fap":            from ..core.auth import cmd_fap; cmd_fap(rest[0] if rest else None)
    elif cmd == "whoami":         from ..core.auth import cmd_whoami; cmd_whoami()
    elif cmd == "extract":        from ..core.extract import main as m; m()
    elif cmd in ("ics", "run"):   from ..core.schedule import main as m; m()
    elif cmd == "calendar-auth":  from .gcal import cmd_auth; cmd_auth()
    elif cmd == "calendar-sync":  from .gcal import cmd_sync; cmd_sync()
    elif cmd == "notify":         from .notify import run; run(" ".join(rest) if rest else "test")
    elif cmd == "watch-attendance": from .attendwatch import run; run(rest)
    elif cmd == "grades":         from ..core.grades import report; report()
    elif cmd == "grades-detail":  from ..core.grades import detail; detail(raw="--raw" in rest)
    elif cmd == "subjects":       from ..core.subjects import report; report()
    elif cmd == "weekly":         from .notify import run; run("weekly")
    elif cmd == "attendance":     from ..core.attendance import report; report()
    elif cmd == "banrisk":        from ..core.attendance import banrisk; sys.exit(banrisk())
    elif cmd in ("status", "dashboard"): from .dashboard import status; status()
    elif cmd == "all":            from .bot_core import handle; print(handle("all"))
    elif cmd == "week":           from .dashboard import week; week(rest[0] if rest else None)
    elif cmd == "week-exact":     from .dashboard import week_exact; week_exact(rest[0] if rest else None, rest[1] if len(rest) > 1 else None)
    elif cmd == "transcript":     from ..core.transcript import report; report()
    elif cmd == "gpa":            from ..core.transcript import gpa_report; gpa_report()
    elif cmd == "whatif":         from ..core.whatif import run; run(rest[0] if rest else None)
    elif cmd == "exams":          from ..core.extras import exams; exams()
    elif cmd == "exams-ics":      from ..core.extras import exams_ics; exams_ics()
    elif cmd == "news":           from ..core.extras import news; news()
    elif cmd == "fees":           from ..core.extras import fees; fees()
    elif cmd == "notifications":  from ..core.extras import notifications; notifications()
    elif cmd == "profile":        from ..core.extras import profile; profile()
    elif cmd == "applications":   from ..core.extras import applications; applications()
    elif cmd == "watch-grades":   from .gradewatch import run; run(rest)
    elif cmd == "web":            from .webui import run; run(rest[0] if rest else 8000)
    elif cmd == "telegram-bot":   from .telegrambot import main as m; m()
    elif cmd == "discord-bot":    from .discordbot import main as m; m()
    elif cmd == "doctor":         doctor()
    elif cmd == "selftest":       sys.exit(selftest())
    else: print(HELP)

if __name__ == "__main__":
    main()
