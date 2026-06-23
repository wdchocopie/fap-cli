# Cấu hình `.env` · `.env` reference

**VI —** Đây là tài liệu chuẩn cho file `.env`. fap-cli **không** dùng `python-dotenv` — nó tự đọc `.env` dạng `KEY=VALUE` (xem `fapc/config.py` và `fapc/__init__.py`). Chỉ những khóa liệt kê dưới đây mới được đọc.
**EN —** This is the authoritative `.env` reference. fap-cli does **not** use `python-dotenv` — it parses `.env` as plain `KEY=VALUE` itself (see `fapc/config.py` and `fapc/__init__.py`). Only the keys listed below are read.

## File `.env` nằm ở đâu · Where `.env` lives

**VI —** `.env` nằm ở **gốc repo** (cùng cấp với `requirements.txt`, `credentials.json`). Đường dẫn được tính từ vị trí package: `<gốc repo>/.env`. Nó được **tự động nạp khi import `fapc`**, trong `fapc/__init__.py`, **trước khi** mọi submodule chạy — nhờ vậy `FAP_SEMESTER` đã có sẵn khi `api.py` cần. Nếu không có file `.env`, fap-cli chạy bình thường với giá trị mặc định.
**EN —** `.env` lives at the **repo root** (next to `requirements.txt`, `credentials.json`). Its path is derived from the package location: `<repo-root>/.env`. It is **loaded automatically on `import fapc`**, inside `fapc/__init__.py`, **before** any submodule runs — so `FAP_SEMESTER` is already visible by the time `api.py` needs it. If `.env` is absent, fap-cli still runs with defaults.

> **VI —** `.env` nằm trong `.gitignore` — chứa token/PII, **không bao giờ commit**. Dùng `.env.example` làm mẫu.
> **EN —** `.env` is `.gitignore`d — it holds tokens/PII, **never commit it**. Use `.env.example` as a template.

## Quy tắc ưu tiên: OS thắng `.env` · Precedence: OS env wins over `.env`

**VI —** Bộ nạp dùng `os.environ.setdefault(key, value)`. Nghĩa là: nếu một khóa **đã tồn tại trong biến môi trường thật của hệ điều hành**, giá trị OS **được giữ** và dòng trong `.env` **bị bỏ qua**. `.env` chỉ điền vào những khóa **chưa** được set. Muốn ép tạm thời, cứ set biến môi trường trước khi chạy `fap`.
**EN —** The loader uses `os.environ.setdefault(key, value)`. So if a key **already exists in the real OS environment**, the OS value **wins** and the `.env` line is **ignored**. `.env` only fills in keys that are **not** already set. To override on the fly, set the OS env var before running `fap`.

```bash
# VI — biến OS thắng giá trị trong .env cho lần chạy này
# EN — OS env var beats the .env value for this one run
FAP_LANG=en fap whoami          # bash / macOS / Linux
```

```powershell
# Windows PowerShell
$env:FAP_LANG = "en"; fap whoami
```

## Bảng khóa `.env` · `.env` key table

| Khóa · Key | Mặc định · Default | Ý nghĩa · Meaning | Ví dụ · Example |
|---|---|---|---|
| `FAP_LANG` | `vi` | Ngôn ngữ thông báo/log · UI/log language. Chỉ `vi` hoặc `en` · only `vi` or `en` | `FAP_LANG=vi` |
| `FAP_SEMESTER` | *(trống · empty)* | Học kỳ. Trống = tự dò qua `GetSemester` theo ngày · semester; empty = auto-detect via `GetSemester` by date. Điền để ép · set to force | `FAP_SEMESTER=Spring2026` |
| `TELEGRAM_TOKEN` | *(trống · empty)* | Token bot Telegram từ BotFather; trống = tắt kênh Telegram · Telegram bot token from BotFather; empty = Telegram disabled | `TELEGRAM_TOKEN=123456:ABC-DEF...` |
| `TELEGRAM_CHAT` | *(trống · empty)* | ID chat/kênh nhận thông báo · target chat/channel id for notifications | `TELEGRAM_CHAT=987654321` |
| `DISCORD_WEBHOOK_URL` | *(trống · empty)* | Webhook Discord (push 1 chiều `notify`); trống = tắt kênh Discord · Discord webhook for one-way `notify` push; empty = disabled | `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...` |
| `GCAL_CALENDAR_ID` | `primary` | Lịch Google đích cho `calendar-sync` · target Google Calendar for `calendar-sync`. `primary` = lịch chính · main calendar | `GCAL_CALENDAR_ID=primary` |
| `DISCORD_BOT_TOKEN` | *(trống · empty)* | Token **bot** Discord cho `fap discord-bot` (KHÁC webhook URL) · Discord **bot** token for `fap discord-bot` (≠ webhook URL) | `DISCORD_BOT_TOKEN=MTk4N...` |
| `DISCORD_ALLOWED_USER_ID` | *(trống · empty)* | Chỉ user này được bot Discord trả lời; trống = trả lời mọi người (**nên đặt**) · only this user the Discord bot answers; empty = replies to everyone (**set it**) | `DISCORD_ALLOWED_USER_ID=123456789012345678` |
| `FAP_WATCH_ABSENT_ONLY` | *(trống · empty)* | `1`/`true` = `watch-attendance` **chỉ báo buổi vắng/muộn** (đỡ spam); trống = báo mọi buổi mới · `1`/`true` = the watcher only pings Absent/Late; empty = ping every new record | `FAP_WATCH_ABSENT_ONLY=1` |
| `FAP_CACHE_MIN` | `0` *(tắt)* | Số **phút** cache phản hồi API trong bộ nhớ (giảm gọi lại endpoint giống nhau). Hữu ích cho `fap web`/`status`. Đặt nhỏ để dữ liệu không cũ · minutes to cache API responses in-memory; small value keeps data fresh | `FAP_CACHE_MIN=5` |
| `FAP_EXTRACT_DELAY` | `0.7` | Số **giây** nghỉ giữa mỗi lượt gọi API khi `fap extract` (lịch sự với server / nhẹ máy yếu) · seconds to pause between API calls during `fap extract` | `FAP_EXTRACT_DELAY=1.5` |
| `DISCORD_ALLOW_ANYONE` | *(trống · empty)* | `1` = cho `fap discord-bot` chạy **dù chưa đặt** `DISCORD_ALLOWED_USER_ID` (bot trả lời **MỌI người** — NGUY HIỂM, lộ dữ liệu); trống = bắt buộc có allowlist · `1` lets the Discord bot run without an allowlist (replies to **everyone** — risky); empty = allowlist required | `DISCORD_ALLOW_ANYONE=1` |

**VI —** Để trống `TELEGRAM_TOKEN`/`TELEGRAM_CHAT`/`DISCORD_WEBHOOK_URL` thì kênh đó **tắt** — `fap notify` đơn giản không gửi qua kênh chưa cấu hình.
**EN —** Leaving `TELEGRAM_TOKEN`/`TELEGRAM_CHAT`/`DISCORD_WEBHOOK_URL` empty simply **disables** that channel — `fap notify` won't push over an unconfigured channel.

### Giá trị `FAP_SEMESTER` hợp lệ · Valid `FAP_SEMESTER` values

**VI —** Dạng `<Mùa><Năm>` không có khoảng trắng, ví dụ `Spring2026`, `Summer2026`, `Fall2026`. Để trống để fap-cli tự dò theo ngày hiện tại.
**EN —** Form `<Season><Year>` with no space, e.g. `Spring2026`, `Summer2026`, `Fall2026`. Leave empty to let fap-cli auto-detect by today's date.

## TZID không phải khóa `.env` · TZID is not an `.env` key

**VI —** Múi giờ **được gán cứng trong code**: `TZID = "Asia/Ho_Chi_Minh"` (trong `fapc/config.py`). Đây **không** phải biến môi trường — đặt nó trong `.env` sẽ **không** có tác dụng.
**EN —** The timezone is **hard-coded**: `TZID = "Asia/Ho_Chi_Minh"` (in `fapc/config.py`). It is **not** an env var — putting it in `.env` has **no** effect.

## Ví dụ `.env` đầy đủ · Full example `.env`

```dotenv
# Sao chép thành .env rồi điền. KHÔNG commit file .env.
# Copy to .env and fill in. DO NOT commit .env.

# Ngôn ngữ thông báo/log · UI/log language: vi | en
FAP_LANG=vi

# Học kỳ — để trống = tự dò qua GetSemester. Ép: vd Spring2026
# Semester — empty = auto-detect via GetSemester. Force: e.g. Spring2026
FAP_SEMESTER=

# Telegram (BotFather cho TOKEN; CHAT = id chat/kênh)
# Telegram (BotFather gives TOKEN; CHAT = chat/channel id)
TELEGRAM_TOKEN=
TELEGRAM_CHAT=

# Discord (Server Settings → Integrations → Webhooks → New Webhook → Copy URL)
DISCORD_WEBHOOK_URL=

# Google Calendar (primary = lịch chính · main calendar)
GCAL_CALENDAR_ID=primary

# Bot tương tác · interactive bots (fap telegram-bot / fap discord-bot)
# Telegram bot dùng lại TELEGRAM_TOKEN + TELEGRAM_CHAT ở trên (CHAT bắt buộc).
# Telegram bot reuses TELEGRAM_TOKEN + TELEGRAM_CHAT above (CHAT required).
DISCORD_BOT_TOKEN=
DISCORD_ALLOWED_USER_ID=
```

**VI —** Sau khi sửa `.env`, kiểm tra nhanh bằng `fap doctor` để xem cấu hình đã được nạp đúng chưa.
**EN —** After editing `.env`, sanity-check with `fap doctor` to confirm the config loaded correctly.

> **VI —** Nhắc lại: `.env`, `credentials.json` và toàn bộ thư mục `output/` đều `.gitignore` vì chứa secret/PII.
> **EN —** Reminder: `.env`, `credentials.json`, and the whole `output/` folder are all `.gitignore`d because they hold secrets/PII.
