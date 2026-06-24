# Triển khai tự động · Deployment

**VI —** Script **sẵn dùng** để chạy fap-cli theo lịch. Hướng dẫn chi tiết: [../docs/14-deploy.md](../docs/14-deploy.md).
**EN —** **Ready-to-use** scripts to run fap-cli on a schedule. Full guide: [../docs/14-deploy.md](../docs/14-deploy.md).

> **VI —** Đăng nhập **1 lần** trên máy thật trước: `fap login`. Mọi job định kỳ chỉ cần `fap refresh` (headless) — script đã lo. Khi `refresh_token` hết hạn → `fap login` lại.
> **EN —** Log in **once** on a real machine first: `fap login`. Scheduled jobs only need `fap refresh` (headless) — the scripts handle it. When the `refresh_token` expires → `fap login` again.

## Mỗi job làm gì · What each job does
`fap refresh` → `fap calendar-sync` → `fap notify today`, **dừng nếu `refresh` lỗi** (không sync/notify bằng token cũ). Log: `output/deploy.log`.

## File · Files
| File | Nền tảng · Platform | Dùng cho · Use |
|---|---|---|
| **`setup-server.sh`** | **Linux server** | **TỰ DỰNG TẤT CẢ bằng 1 lệnh**: venv + cài + systemd (job hằng ngày + watch-attendance + watch-grades + bot tùy chọn) · **one-command full server setup** |
| **`update.sh`** | **Linux server** | **CẬP NHẬT bằng 1 lệnh**: `git pull` + cài lại + selftest + restart service đang bật · **one-command update** |
| `run-fap.ps1` | Windows (PowerShell) | wrapper có log + dừng-khi-lỗi · logging wrapper |
| `run-fap.cmd` | Windows (cmd) | wrapper gọn cho `schtasks` · simple wrapper |
| `register-task-windows.ps1` | Windows | đăng ký Scheduled Task hằng ngày (mặc định 07:00) · register the daily task |
| `register-watch-windows.ps1` | Windows | **service thường trú**: watcher điểm danh chạy ngầm khi đăng nhập (ẩn, tự refresh) · resident attendance watcher |
| `run-fap.sh` | Linux/macOS | wrapper có log + dừng-khi-lỗi · logging wrapper |
| `run-notify.ps1` / `run-notify.sh` | Windows / Linux | refresh + gửi **1 view** (`today`/`weekly`/`banrisk`…) — cho lịch thông báo riêng · push one view |
| `crontab.example` | Linux/macOS | dòng cron mẫu (đã kèm lịch đề xuất) · sample cron lines |
| `fap.service` + `fap.timer` | Linux (systemd) | job hằng ngày: refresh+sync+notify · daily one-shot |
| `fap-bot.service` | Linux (systemd) | bot Telegram thường trú (auto-restart) · resident interactive bot |
| `fap-watch.service` | Linux (systemd) | theo dõi điểm danh near-real-time (auto-restart) · resident attendance watcher |
| `fap-gradewatch.service` | Linux (systemd) | theo dõi **điểm mới** (thành phần/tổng kết, auto-restart) · resident grade watcher |
| `Dockerfile` + `docker-run.sh` + `../.dockerignore` | Docker | đóng gói (tùy chọn) · container (optional) |

## Bắt đầu nhanh · Quickstart

**🚀 Linux server — TỰ DỰNG TẤT CẢ (1 lệnh)**
```bash
# 1) (TRÊN MÁY CÓ BROWSER) đăng nhập, rồi copy token lên server:
fap login && scp -r output/ <user>@<server>:~/fap-cli/
# 2) (TRÊN SERVER, ở gốc repo) dựng hết:
bash deploy/setup-server.sh                       # job hằng ngày + 2 watcher
EXTRAS='[gcal,bot]' bash deploy/setup-server.sh   # + bot Telegram thường trú
# Gỡ sạch:  bash deploy/setup-server.sh --remove
```
**🔄 Cập nhật về sau (1 lệnh):**
```bash
bash deploy/update.sh                       # git pull + cài lại + selftest + restart service đang bật
EXTRAS='[gcal,bot]' bash deploy/update.sh   # khớp extras lúc setup
```
> Hoặc gọn hơn: `fap update` (chỉ `git pull`; bản cài `-e` có hiệu lực ngay — nhớ restart bot/watcher để nạp mã mới).
> Script tự: tạo `.venv`, `pip install -e .`, kiểm `fap refresh`, cài systemd `--user` units (đường dẫn thật), bật `enable-linger` (chạy cả khi logout). **Bước login phải làm trên máy có trình duyệt** (OAuth Google) rồi copy `output/` lên — server headless không tự login được.

**Windows** *(PowerShell ở gốc repo · from repo root)*
```powershell
.\deploy\run-fap.ps1                       # chạy thử 1 lượt · test one pass
.\deploy\register-task-windows.ps1 -Time 07:00   # lên lịch hằng ngày · schedule daily
```

**Linux/macOS**
```bash
chmod +x deploy/run-fap.sh deploy/docker-run.sh
./deploy/run-fap.sh                        # chạy thử · test one pass
crontab -e                                 # rồi dán 1 dòng từ crontab.example · paste a line
# systemd: copy fap.service + fap.timer -> ~/.config/systemd/user/ ; sửa đường dẫn · edit paths
#          systemctl --user daemon-reload && systemctl --user enable --now fap.timer
```

**Docker** *(tùy chọn · optional, build từ gốc repo · build from repo root)*
```bash
./deploy/docker-run.sh                     # build + run, mount .env/credentials/output từ host
```

## 🗓️ Lịch thông báo đề xuất · Recommended notification schedule

| Khi nào · When | Lệnh · Command | Mục đích · Why |
|---|---|---|
| 06:30 T2–T7 · Mon–Sat | `run-notify today` | lịch hôm nay trước khi đi học · today before class |
| 21:00 CN–T5 · Sun–Thu | `run-notify tomorrow` | xem trước ngày mai · plan tomorrow |
| 20:00 Chủ nhật · Sun | `run-notify weekly` | tổng quan tuần tới · week ahead |
| 18:00 Thứ 6 · Fri | `run-notify banrisk` | cảnh báo cấm thi sau tuần học · exam-ban check |
| *(tùy chọn)* 12:00 T2 · Mon | `run-notify attendance` | điểm danh đầu tuần · attendance recap |

**Linux/macOS** — đã có sẵn trong [`crontab.example`](crontab.example): `crontab -e` rồi dán.
**Windows** — mỗi mốc là một task (đổi `/D`, `/ST`), ví dụ cảnh báo cấm thi tối Thứ 6:
```bat
schtasks /Create /TN "FAP banrisk" /SC WEEKLY /D FRI /ST 18:00 /F ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\fap-cli\deploy\run-notify.ps1 banrisk"
schtasks /Create /TN "FAP today" /SC DAILY /ST 06:30 /F ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\fap-cli\deploy\run-notify.ps1 today"
```

> **VI —** Điểm danh trên FAP cập nhật **sau mỗi buổi** → kiểm cuối tuần (T6) là đủ sớm để xử lý. Đừng hẹn mỗi phút/giờ — gọi nhẹ tay.
> **EN —** FAP attendance updates **after each class** → a Friday check is early enough to act on. Don't schedule per-minute/hour — be gentle.

> 🔔 **VI —** Muốn báo **ngay khi vừa được điểm danh**? Dùng `fap watch-attendance` (dò thay đổi `Future→Present`). KHÔNG có "tức thì thật" (FAP không đẩy) — độ trễ ≈ chu kỳ dò. Chạy nền: [`fap-watch.service`](fap-watch.service) (`loop 15`).
> 🔔 **EN —** Want a ping **the moment attendance is recorded**? Use `fap watch-attendance` (detects the `Future→Present` flip). No true real-time (FAP has no push) — latency ≈ the poll interval. Resident: [`fap-watch.service`](fap-watch.service) (`loop 15`).

> 🎯 **VI —** Muốn báo **khi vừa có ĐIỂM MỚI** (thành phần/tổng kết)? Dùng `fap watch-grades` (so điểm với lần trước, mỗi điểm chỉ báo 1 lần). Chạy nền: [`fap-gradewatch.service`](fap-gradewatch.service) (`loop 60` — điểm đổi chậm). Windows: đổi argline trong `register-watch-windows.ps1` thành `-m fapc watch-grades loop 60`.
> 🎯 **EN —** Want a ping **when a new mark appears** (component/final)? Use `fap watch-grades`. Resident: [`fap-gradewatch.service`](fap-gradewatch.service) (`loop 60` — grades change slowly). Windows: change the argline in `register-watch-windows.ps1` to `-m fapc watch-grades loop 60`.

## 🪟 Service thường trú trên Windows · Resident service on Windows
**VI —** Watcher chạy ngầm (ẩn cửa sổ `pythonw`, tự khởi động khi đăng nhập, tự refresh token, auto-restart):
**EN —** Run the watcher in the background (hidden `pythonw`, starts at logon, self-refreshes the token, auto-restart):
```powershell
.\deploy\register-watch-windows.ps1                 # 15', chỉ báo vắng · 15m, absent-only
.\deploy\register-watch-windows.ps1 -Interval 10 -AllNew
# Gỡ · remove:
Unregister-ScheduledTask -TaskName 'FAP Attendance Watch' -Confirm:$false
```
> **VI —** Cùng cách cho **bot** Telegram: sửa argline trong script thành `-m fapc telegram-bot`. (Windows không có systemd; đây là tương đương `fap-watch.service`.)
> **EN —** Same pattern for the Telegram **bot**: change the argline to `-m fapc telegram-bot`. (Windows has no systemd; this is the equivalent of `fap-watch.service`.)

## 🎚️ Profile theo cấu hình máy · Profiles (weak → strong)

| Profile | Cài · Install | Thông báo · Notify | Điểm danh · Attendance | Ghi chú |
|---|---|---|---|---|
| 🪶 **Lite** (máy yếu) | `pip install -e .` (chỉ `requests`) | `run-notify` **theo lịch** (cron/Task) | `watch-attendance` **một-lượt** mỗi 20–30' | đặt `FAP_CACHE_MIN=5`; chỉ Telegram |
| ⚖️ **Standard** | `pip install -e ".[gcal]"` | scheduled + `calendar-sync` | watcher `loop 15 --absent-only` (resident) | thêm Google Calendar |
| 🚀 **Full** (máy khỏe) | `pip install -e ".[gcal,bot]"` | bot tương tác + `fap web` | watcher `loop 10` (resident) | bot Telegram/Discord + dashboard + `watch-grades loop 60` |

## 🪶 Máy yếu / ít tài nguyên · Low-resource machines
**VI —** Tránh tiến trình **thường trú**; ưu tiên **one-shot theo lịch** (Python chạy rồi thoát, không giữ RAM):
- **Cài tối giản**: chỉ `pip install -e .` (chỉ cần `requests`) — KHÔNG cài `[gcal]`/`[bot]` (nặng) nếu không dùng.
- Dùng **Telegram** (thuần `requests`) thay vì **Discord bot** (`discord.py` nặng + giữ kết nối WebSocket).
- Điểm danh: hẹn `fap watch-attendance` **một-lượt** mỗi 20–30' bằng Task Scheduler/cron, thay vì `loop` thường trú.
- Thông báo: dùng `run-notify` **theo lịch** thay vì bot tương tác.

**EN —** Avoid **resident** processes; prefer **scheduled one-shots** (Python runs then exits, no held RAM):
- **Minimal install**: just `pip install -e .` (only `requests`) — skip the heavy `[gcal]`/`[bot]` extras.
- Prefer **Telegram** (pure `requests`) over the **Discord bot** (`discord.py` + persistent gateway).
- Attendance: schedule a **one-shot** `fap watch-attendance` every 20–30 min instead of a resident `loop`.
- Notifications: use scheduled `run-notify` instead of an interactive bot.

## ⚠️ An toàn · Safety
- **VI —** Bí mật (`.env`, `output/`, `credentials.json`) **mount/đọc tại chỗ**, KHÔNG bake vào image, KHÔNG commit. `.dockerignore` đã loại chúng khỏi build context.
  **EN —** Secrets are mounted/read in place, never baked into the image or committed. `.dockerignore` keeps them out of the build context.
- **VI —** Lên lịch **nhẹ tay** (vài lần/ngày). Chỉ tài khoản của bạn. · **EN —** Schedule gently (a few times/day). Your own account only.
