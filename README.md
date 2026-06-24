# fap-cli — lấy dữ liệu FAP (FPT) bằng tài khoản của bạn

![Python](https://img.shields.io/badge/python-3.7%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Status](https://img.shields.io/badge/FPT-unofficial-orange)

Công cụ Python giúp **sinh viên FPT** đăng nhập FAP qua **Google OAuth (FE Identity)** rồi kéo dữ liệu
học tập của **chính mình** (lịch học, điểm, điểm danh, học phí, thông báo...) và xuất lịch ra Google Calendar.
**Không cần máy ảo.** Reverse-engineer từ app chính thức (`com.fuct`, React Native + Hermes).

> ⚠️ **Dự án KHÔNG chính thức.** SECRET/clientId dùng trong code trích từ APK công khai. Chỉ dùng cho
> **tài khoản & dữ liệu của chính bạn** — đừng quét MSSV người khác, đừng gọi dồn dập server trường.

## Yêu cầu · Requirements
- Python **3.7+**
- `pip install -e .`  → cài package + lệnh **`fap`** (hoặc `pip install -r requirements.txt` rồi dùng `python -m fapc`).
- Google Calendar (tuỳ chọn): `pip install -e ".[gcal]"` hoặc `pip install -r requirements-gcal.txt`.

## Quickstart (từ thư mục gốc repo · from repo root)
```bash
pip install -e .

fap campuses     # (tuỳ chọn) xem campusCode của bạn, vd FPTU · list campus codes (no login needed)
fap login        # đăng nhập Google @fpt.edu.vn 1 lần · one-time Google login → output/token.json
fap status       # xem thử tổng quan hôm nay · quick today overview
fap extract      # kéo toàn bộ dữ liệu · pull all data → output/
fap ics          # xuất · export output/lichhoc.ics
fap refresh      # các lần sau: làm mới token (không cần browser) · headless token refresh
```
- `campuses`: chạy được **trước khi login** — để biết `CampusCode` cần nhập lúc `fap login`.
- `login`: mở trình duyệt → đăng nhập → nếu báo `scheme not registered` là **đúng**, copy URL dán lại.
- Học kỳ **tự nhận** theo tài khoản + ngày (Spring/Summer/Fall) — bất kỳ sinh viên, kỳ nào cũng chạy; ép bằng `FAP_SEMESTER` nếu cần.
- Import lịch · Import calendar: Google Calendar → **Settings → Import & Export** → `output/lichhoc.ics`.
- Đẩy thẳng lên Google Calendar · push directly: `fap calendar-auth` rồi `fap calendar-sync`.
- Gửi lên Telegram/Discord · push to chat: cấu hình `.env` (xem `.env.example`) rồi `fap notify today`.
- Xem nhanh · quick view: `fap status` (tổng quan hôm nay · today overview), `fap week` (lịch tuần · weekly), `fap whatif 8` (mô phỏng GPA · GPA what-if).
- Hiện **tên môn** thay vì mã trơ: chạy `fap subjects` **một lần** → tên + tín chỉ xuất hiện ở grades/điểm danh/lịch/bot/web (và GPA kỳ tính **theo tín chỉ**). · run `fap subjects` once → names + credits everywhere.
- Tổng kết tuần 1 tin · weekly recap: `fap weekly` (lịch + điểm danh + điểm → kênh chat).
- Lớp đang học · my classes: `fap courses` (môn / lớp / giảng viên / phòng — `GetCourseOfSemester`, fallback từ TKB).

Mọi lệnh · all commands: `fap` (không tham số). Cơ chế OAuth: [docs/04-feid-oauth-tool.md](docs/04-feid-oauth-tool.md).

## 📚 Tài liệu · Documentation
Mục lục đầy đủ · full index: **[docs/README.md](docs/README.md)**.

| | |
|---|---|
| [Cài đặt & quickstart](docs/10-install.md) · [Tham chiếu lệnh `fap`](docs/11-commands.md) | bắt đầu · getting started |
| [Google Calendar](docs/12-google-calendar.md) · [Telegram/Discord](docs/13-notify.md) · [Tự động hóa](docs/14-deploy.md) | tính năng · features |
| [Cấu hình `.env`](docs/15-config.md) · [Khắc phục sự cố](docs/16-troubleshooting.md) | tham chiếu · reference |
| [Bảo mật · Security](SECURITY.md) · [Giấy phép · License (MIT)](LICENSE) | tài nguyên · resources |

## Cấu hình · Config (`.env` ở gốc repo — copy từ `.env.example`)
| | |
|---|---|
| `FAP_LANG` | `vi` (mặc định) \| `en` — ngôn ngữ thông báo · notification language |
| `FAP_SEMESTER` | để trống = tự dò · empty = auto-detect; ép · force: `Spring2026` |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT` / `DISCORD_WEBHOOK_URL` | kênh notify · notify channels |
| Console Windows lỗi font | `chcp 65001` hoặc · or `PYTHONUTF8=1` (package cũng tự `reconfigure utf-8`) |

## Cấu trúc · Structure
```
fap-cli/
├── pyproject.toml · requirements.txt · .env.example
├── fapc/                    ← package (lệnh `fap` / `python -m fapc`)
│   ├── __init__.py · config.py · i18n.py · fmt.py   ← shared (nạp .env, cấu hình, song ngữ, định dạng)
│   ├── core/                ← LÕI: truy cập dữ liệu — KHÔNG phụ thuộc app
│   │   ├── api.py           ← creds + checksum + call + auto học kỳ
│   │   ├── auth.py          ← đăng nhập OAuth (login/refresh/exchange/whoami)
│   │   └── schedule.py · grades.py · attendance.py · transcript.py · whatif.py · subjects.py · courses.py · extras.py · extract.py
│   └── app/                 ← APP: kết nối người dùng — phụ thuộc core
│       ├── cli.py           ← điểm vào CLI · CLI entry
│       ├── gcal.py          ← Google Calendar sync (OAuth)
│       ├── notify.py        ← Telegram + Discord (push 1 chiều)
│       ├── bot_core.py · telegrambot.py · discordbot.py   ← bot tương tác (menu/slash + nhắc trước tiết)
│       ├── reminders.py     ← nhắc trước mỗi tiết (trong bot)
│       ├── webui.py · dashboard.py   ← web dashboard / status / week
│       └── attendwatch.py · gradewatch.py   ← theo dõi điểm danh / điểm near real-time
├── deploy/                  ← script lên lịch · scheduling (Windows/cron/systemd/Docker)
├── legacy/                  ← cách CŨ · legacy (fap_login mật khẩu, pull_token máy ảo)
├── docs/                    ← tài liệu + ghi chép reverse-engineering
├── tests/                   ← test offline (`test_logic.py`) + smoke test LIVE (`live_smoke.py`)
└── output/                  ← KẾT QUẢ (token + dữ liệu cá nhân — đã .gitignore)
```

## ✅ Kiểm thử & CI · Tests & CI
- **Chạy toàn bộ test offline** (không cần token/mạng): **`fap selftest`** — hoặc `python tests/test_logic.py` + `python tests/integration_offline.py` (**53 unit + 79 integration**, mọi lời gọi API đều mock).
- Repo kèm sẵn **GitHub Actions** ([.github/workflows/tests.yml](.github/workflows/tests.yml)): tự chạy 2 bộ test trên **Python 3.8–3.13** mỗi khi `push`/PR. Sau khi đẩy repo lên GitHub, gắn badge (thay `OWNER/REPO` bằng repo của bạn):
  ```
  [![tests](https://github.com/OWNER/REPO/actions/workflows/tests.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/tests.yml)
  ```

## 🔒 Trước khi public repo (đọc kỹ)
> 📄 Bản đầy đủ (song ngữ) · full bilingual version: **[SECURITY.md](SECURITY.md)**.

`output/` chứa **token, refresh_token và dữ liệu cá nhân** (điểm, học bạ, CCCD, phụ huynh...). Đã được
`.gitignore`, nhưng:
- Chạy `git status` trước khi commit — **không** thấy `output/`, `device-data/`, `credentials.json`.
- **Đừng** `git add -f` các thứ trên.
- Nếu lỡ commit token: **xoá khỏi lịch sử git** (vd `git filter-repo`) **và** đăng xuất app/FE Identity để vô hiệu token.
- Không log token ra nơi công khai; không chia sẻ thư mục `output/`.

## Lưu ý
- Chỉ tài khoản của bạn. Gọi nhẹ nhàng (script đã giãn cách + cache theo giờ).
- Trường có thể đổi secret/endpoint bất kỳ lúc nào → công cụ có thể hỏng, cần cập nhật.
- Tránh các endpoint GHI dữ liệu (AddRate, UpdateToken...).
