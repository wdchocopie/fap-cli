# Tự động hóa định kỳ · Scheduling & automation

**VI —** Trang này hướng dẫn chạy fap-cli **theo lịch** (Task Scheduler / cron / systemd / Docker) để tự kéo dữ liệu, đồng bộ lịch và gửi nhắc — không phải bấm tay mỗi ngày.
**EN —** This page shows how to run fap-cli **on a schedule** (Task Scheduler / cron / systemd / Docker) so it pulls data, syncs your calendar, and pushes reminders without manual runs.

> **VI —** Chỉ dùng cho **tài khoản của chính bạn**. Lên lịch **nhẹ tay** (vài lần/ngày), đừng dội liên tục vào server FAP.
> **EN —** Your **own account only**. Schedule **gently** (a few times a day) — never hammer the FAP server.

> ⚡ **VI —** **Script sẵn dùng** đã có trong [`deploy/`](../deploy/) (xem [deploy/README.md](../deploy/README.md)) — không cần gõ tay theo các mục dưới: `run-fap.ps1`/`run-fap.cmd` + `register-task-windows.ps1` (Windows), `run-fap.sh`/`crontab.example`/`fap.service`+`fap.timer` (Linux), `Dockerfile`+`docker-run.sh` (Docker). Các mục dưới giải thích từng cách.
> ⚡ **EN —** **Ready-made scripts** already live in [`deploy/`](../deploy/) (see [deploy/README.md](../deploy/README.md)) — you don't have to type the recipes below by hand. The sections below explain each method.

---

## 1. Vòng đời token · Token lifecycle

**VI —** Phải hiểu rõ chỗ này trước khi lên lịch, vì máy chạy nền **không mở được trình duyệt**.
**EN —** Understand this before scheduling, because a headless box **cannot open a browser**.

| Bước · Step | Lệnh · Command | Tương tác? · Interactive? | Khi nào · When |
|---|---|---|---|
| Đăng nhập lần đầu · First login | `fap login` (+ `fap exchange "<url>"` nếu cần) | **Có · Yes** (mở trình duyệt, login Google) | 1 lần lúc cài · once at setup |
| Làm mới trước mỗi lần kéo · Renew before each pull | `fap refresh` | **Không · No** (headless, dùng `refresh_token`) | đầu mỗi job theo lịch · start of every scheduled job |
| Đăng nhập lại · Re-login | `fap login` | **Có · Yes** | khi `refresh_token` hết hạn · when the refresh token expires |

**VI —** Luồng chuẩn: `fap login` **một lần** (mở trình duyệt, login Google `@fpt.edu.vn`; trình duyệt báo `scheme ... not registered` là **bình thường** — copy URL ở thanh địa chỉ rồi dán vào prompt hoặc chạy `fap exchange "<url>"`). Sau đó mọi job định kỳ chỉ cần `fap refresh` (không trình duyệt) là đủ — cho tới khi `refresh_token` hết hạn thì `fap login` lại.
**EN —** Standard flow: `fap login` **once** (browser opens, log in with Google `@fpt.edu.vn`; the browser then shows `scheme ... not registered` — **this is normal** — copy the address-bar URL and paste it at the prompt or run `fap exchange "<url>"`). After that, every scheduled job only needs `fap refresh` (no browser) — until the `refresh_token` expires, at which point you `fap login` again.

> **VI —** `fap refresh` đọc `output/oauth_tokens.json` (chứa `refresh_token`) → cấp `access_token` mới → đổi lấy token FAP (`output/token.json`). Nếu nó báo `Refresh lỗi ... refresh_token hết hạn?` thì job nền sẽ dừng — đó là tín hiệu bạn phải đăng nhập lại bằng tay.
> **EN —** `fap refresh` reads `output/oauth_tokens.json` (holds the `refresh_token`) → mints a fresh `access_token` → exchanges it for the FAP token (`output/token.json`). If it prints `Refresh lỗi ... refresh_token hết hạn?`, the headless job stops — that is your cue to re-login interactively.

**VI —** Mẹo kiểm tra nhanh trước khi giao cho máy nền:
**EN —** Quick sanity check before handing it to a scheduler:

```bash
fap whoami     # token FAP đã lưu chưa · is the FAP token saved
fap doctor     # Python, token.json, .env, requests, kênh notify · environment self-check
```

---

## 2. Thứ tự lệnh trong một job · Order of commands in one job

**VI —** Một lượt chạy định kỳ điển hình, **đúng thứ tự này**:
**EN —** A typical scheduled run, **in this exact order**:

```bash
fap refresh          # 1) làm mới token (headless)        · renew token (headless)
fap calendar-sync    # 2) đẩy lịch lên Google Calendar    · push schedule to Google Calendar
fap notify today     # 3) gửi nhắc lịch hôm nay           · send today's reminder
```

**VI —** Tùy nhu cầu thêm `fap extract` (kéo toàn bộ JSON về `output/api/`), `fap ics` (xuất `output/lichhoc.ics`), hoặc `fap banrisk` (cảnh báo cấm thi — xem §7).
**EN —** Optionally add `fap extract` (dump all JSON to `output/api/`), `fap ics` (export `output/lichhoc.ics`), or `fap banrisk` (exam-ban alert — see §7).

> **VI —** Mọi lệnh chạy từ **thư mục gốc repo** (nơi có `.env`, `credentials.json`, thư mục `output/`). Nếu chưa cài `pip install -e .`, thay `fap` bằng `python -m fapc`.
> **EN —** Run every command from the **repo root** (where `.env`, `credentials.json`, and `output/` live). If you have not run `pip install -e .`, replace `fap` with `python -m fapc`.

---

## 3. Windows — Task Scheduler

**VI —** Nhanh nhất: dùng script sẵn trong `deploy\`. Mở **PowerShell ở gốc repo**:
**EN —** Quickest: use the ready scripts in `deploy\`. Open **PowerShell at the repo root**:

```powershell
.\deploy\run-fap.ps1                               # chạy thử 1 lượt · test one pass
.\deploy\register-task-windows.ps1 -Time 07:00     # đăng ký chạy hằng ngày · register daily
```

**VI —** `register-task-windows.ps1` tạo task "FAP Daily" (đổi `-Time` / `-TaskName` tùy ý), **không cần admin**. Quản lý:
**EN —** `register-task-windows.ps1` creates a "FAP Daily" task (override `-Time` / `-TaskName`), **no admin needed**. Manage it:

```powershell
Start-ScheduledTask      -TaskName 'FAP Daily'                       # chạy ngay · run now
Get-ScheduledTask        -TaskName 'FAP Daily' | Get-ScheduledTaskInfo   # trạng thái · status
Unregister-ScheduledTask -TaskName 'FAP Daily' -Confirm:$false       # xóa · remove
```

**VI —** Thích `cmd`/`schtasks`? Đã có sẵn `deploy\run-fap.cmd`:
**EN —** Prefer `cmd`/`schtasks`? `deploy\run-fap.cmd` is provided:

```bat
schtasks /Create /TN "FAP Daily" /SC DAILY /ST 07:00 /F ^
  /TR "C:\path\to\fap-cli\deploy\run-fap.cmd"
schtasks /Run    /TN "FAP Daily"      :: chạy thử · run now
schtasks /Delete /TN "FAP Daily" /F   :: xóa · delete
```

> **VI —** Cả hai wrapper **tự `cd`** về gốc repo, tự chọn `fap` hoặc `python -m fapc`, ghi log `output\deploy.log`, và **DỪNG nếu `refresh` lỗi** (không sync/notify bằng token cũ). Tiếng Việt/emoji đã xử lý (`chcp 65001` / `PYTHONUTF8=1`).
> **EN —** Both wrappers **self-`cd`** to the repo root, auto-pick `fap` or `python -m fapc`, log to `output\deploy.log`, and **STOP if `refresh` fails**. UTF-8 handled (`chcp 65001` / `PYTHONUTF8=1`).

---

## 4. Linux — cron

**VI —** Một dòng crontab chạy **mỗi ngày 07:00**. Phải `cd` vào gốc repo trước (các lệnh đọc `.env`, `output/` theo đường dẫn tương đối từ đó).
**EN —** One crontab line, **daily at 07:00**. You must `cd` into the repo root first (commands read `.env`, `output/` relative to it).

> **VI —** Mẫu sẵn: [`deploy/crontab.example`](../deploy/crontab.example) + wrapper [`deploy/run-fap.sh`](../deploy/run-fap.sh) (tự cd + log + dừng nếu refresh lỗi).
> **EN —** Ready samples: [`deploy/crontab.example`](../deploy/crontab.example) + the [`deploy/run-fap.sh`](../deploy/run-fap.sh) wrapper (self-cd + log + stop on refresh failure).

```cron
# m  h  dom mon dow   command
0 7 * * *  cd /home/you/fap-cli && PYTHONUTF8=1 /home/you/.venv/bin/fap refresh && fap calendar-sync && fap notify today >> /home/you/fap-cli/output/cron.log 2>&1
```

**VI —**
- Dùng **đường dẫn tuyệt đối** tới `fap` (hoặc tới `python -m fapc`) vì cron có `PATH` tối thiểu.
- `&&` đảm bảo chỉ sync/notify khi `refresh` thành công.
- Ghi log ra `output/cron.log` để soi khi lỗi.

**EN —**
- Use the **absolute path** to `fap` (or to `python -m fapc`) because cron has a minimal `PATH`.
- `&&` ensures sync/notify only run if `refresh` succeeded.
- Logging to `output/cron.log` makes failures debuggable.

> **VI —** Muốn 2 lần/ngày? Thêm một dòng nữa (vd `0 7` và `0 18`). Đừng đặt mỗi phút/mỗi giờ — token chỉ cần làm mới quanh lúc bạn thật sự xem.
> **EN —** Want twice a day? Add a second line (e.g. `0 7` and `0 18`). Don't go per-minute/per-hour — the token only needs refreshing around when you actually look.

---

## 5. Linux — systemd `.service` + `.timer`

**VI —** Sạch hơn cron: log gom vào `journalctl`, dễ bật/tắt. Tạo cặp file trong `~/.config/systemd/user/`.
**EN —** Cleaner than cron: logs go to `journalctl`, easy to enable/disable. Create a pair in `~/.config/systemd/user/`.

> **VI —** File sẵn: [`deploy/fap.service`](../deploy/fap.service) + [`deploy/fap.timer`](../deploy/fap.timer) — copy vào `~/.config/systemd/user/` rồi sửa đường dẫn.
> **EN —** Ready units: [`deploy/fap.service`](../deploy/fap.service) + [`deploy/fap.timer`](../deploy/fap.timer) — copy to `~/.config/systemd/user/` and edit paths.

**`fap.service`**:

```ini
[Unit]
Description=fap-cli daily pull (vi · en)

[Service]
Type=oneshot
WorkingDirectory=%h/fap-cli
Environment=PYTHONUTF8=1
ExecStart=%h/.venv/bin/fap refresh
ExecStart=%h/.venv/bin/fap calendar-sync
ExecStart=%h/.venv/bin/fap notify today
```

**`fap.timer`**:

```ini
[Unit]
Description=Run fap-cli daily at 07:00 (vi · en)

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**VI —** Bật và kiểm tra · **EN —** Enable and inspect:

```bash
systemctl --user daemon-reload
systemctl --user enable --now fap.timer
systemctl --user list-timers fap.timer     # lần chạy kế tiếp · next run
journalctl --user -u fap.service -n 50      # log gần nhất    · recent logs
```

> **VI —** Nhiều dòng `ExecStart` chạy **tuần tự**; nếu `refresh` lỗi (exit ≠ 0) thì các bước sau **không** chạy — đúng ý ta.
> **EN —** Multiple `ExecStart` lines run **sequentially**; if `refresh` fails (non-zero exit) the later steps **don't** run — which is what we want.

---

## 6. Docker *(tùy chọn · optional)*

**VI —** Chỉ dùng nếu bạn thích đóng gói. **Không bắt buộc** — Task Scheduler/cron đơn giản hơn nhiều.
**EN —** Only if you like containers. **Not required** — Task Scheduler/cron is far simpler.

> **VI —** File sẵn: [`deploy/Dockerfile`](../deploy/Dockerfile) + [`deploy/docker-run.sh`](../deploy/docker-run.sh) (+ `.dockerignore` ở gốc repo). Build từ gốc repo: `docker build -f deploy/Dockerfile -t fapc .`
> **EN —** Ready: [`deploy/Dockerfile`](../deploy/Dockerfile) + [`deploy/docker-run.sh`](../deploy/docker-run.sh) (+ `.dockerignore` at the repo root). Build from the repo root: `docker build -f deploy/Dockerfile -t fapc .`

**`Dockerfile`** (phác thảo · sketch):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUTF8=1
COPY requirements.txt requirements-gcal.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-gcal.txt
COPY . .
RUN pip install --no-cache-dir -e ".[gcal]"
# Lịch chạy 1 lượt rồi thoát · run one pass then exit:
CMD ["sh", "-c", "fap refresh && fap calendar-sync && fap notify today"]
```

**VI —** Mount **bí mật** từ ngoài vào, **đừng** bake vào image:
**EN —** Mount **secrets** from the host, **don't** bake them into the image:

```bash
docker build -t fapc .
docker run --rm \
  -v "$PWD/.env":/app/.env:ro \
  -v "$PWD/credentials.json":/app/credentials.json:ro \
  -v "$PWD/output":/app/output \
  fapc
```

**VI —** Lên lịch bằng cron của **host** gọi `docker run ...` (đơn giản, khuyến nghị), hoặc thêm `cron` vào trong image. Vì cần đăng nhập lần đầu có trình duyệt, hãy chạy `fap login` **trên host** rồi mount `output/` (đã có `token.json` + `oauth_tokens.json`) vào container để `fap refresh` headless dùng lại.
**EN —** Schedule via the **host** cron calling `docker run ...` (simple, recommended), or bake a `cron` into the image. Because first login needs a browser, run `fap login` **on the host**, then mount `output/` (already holding `token.json` + `oauth_tokens.json`) so the container's `fap refresh` can reuse it headlessly.

> **VI —** `output/`, `.env`, `credentials.json` đều nằm trong `.gitignore` (chứa bí mật/PII) — và phải nằm ngoài layer image luôn.
> **EN —** `output/`, `.env`, `credentials.json` are all `.gitignored` (secrets/PII) — keep them out of image layers too.

---

## 7. Cảnh báo cấm thi trong tự động hóa · Exam-ban alerts in automation

**VI —** `fap banrisk` thoát với **exit code 2** khi có môn nguy cơ (chuyên cần < 80%), `0` khi an toàn. Dùng mã thoát này để bật cảnh báo trong cron/CI.
**EN —** `fap banrisk` exits with **code 2** when a subject is at risk (attendance < 80%), and `0` when safe. Use that exit code to trigger an alert in cron/CI.

```bash
fap refresh && fap banrisk || fap notify test   # nếu nguy cơ (exit 2) -> gửi cảnh báo · on risk (exit 2), push an alert
```

> **VI —** Đây là **xấp xỉ**: ngưỡng 80% chuyên cần *hiện tại* chỉ là **proxy** cho luật cấm thi thật của FPT (tính trên **tổng số buổi đã xếp** của kỳ). Hãy coi là cảnh báo sớm, không phải phán quyết chính thức.
> **EN —** This is an **approximation**: the 80%-of-*current*-attendance threshold is only a **proxy** for FPT's real exam-ban rule (which is based on the **total scheduled sessions** for the term). Treat it as an early warning, not an official verdict.

---

## 8. An toàn & lịch sự · Safety & etiquette

| Nguyên tắc · Rule | Chi tiết · Detail |
|---|---|
| Nhẹ tay · Be gentle | vi: vài lần/ngày là đủ, đừng chạy mỗi phút/giờ · en: a few times/day is plenty, never per-minute/hour |
| Của bạn thôi · Yours only | vi: chỉ tài khoản của chính bạn · en: your own account only |
| Bí mật ở đúng chỗ · Keep secrets in place | vi: `.env` + `output/` (`token.json`, `oauth_tokens.json`, `gcal_token.json`) + `credentials.json` · en: in `.env` + `output/` + `credentials.json` |
| Đừng commit/đừng bake · Don't commit/bake | vi: tất cả đã `.gitignore`; đừng nhúng vào image hay log · en: all `.gitignored`; never embed in images or logs |
| Lỗi `refresh` = login lại · Refresh failure = re-login | vi: `refresh_token` hết hạn thì job dừng, chạy `fap login` tay · en: when the refresh token expires the job stops; run `fap login` manually |

> **VI —** Một số endpoint (`GeFeeByRoll`, `GetSemesterMark`, `GetVersion`) có thể trả **404** với tài khoản chưa có kỳ hoàn tất — đó là do dữ liệu/server, **không phải lỗi tool**. (`grades-detail`/`GetMarkByCourse` dùng checksum `cs12(rollNumber, campusCode)` — **đã kiểm chứng live** = `code=200`.)
> **EN —** Some endpoints (`GeFeeByRoll`, `GetSemesterMark`, `GetVersion`) may return **404** for accounts with no completed semesters — that's data/server-driven, **not a tool bug**. (`grades-detail`/`GetMarkByCourse` uses checksum `cs12(rollNumber, campusCode)` — **verified live** = `code=200`.)

---

**VI —** Liên quan · **EN —** See also: `docs/05-checksum-map.md` (checksum), `.env.example` (cấu hình · config), `fap doctor` (tự kiểm tra · self-check).
