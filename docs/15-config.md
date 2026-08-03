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

## File env riêng cho mỗi profile · Per-profile env file

**VI —** Khi chạy **nhiều tài khoản trên cùng 1 máy** (`FAP_PROFILE=alice`), fap-cli nạp **hai** file, đúng thứ tự này:
**EN —** With **several accounts on one box** (`FAP_PROFILE=alice`), fap-cli loads **two** files, in this order:

1. **`<gốc repo>/.env.alice`** — nạp **TRƯỚC** nên **THẮNG** (loader dùng `setdefault`) · loaded **first**, so it **wins**
2. **`<gốc repo>/.env`** — chỉ bù các khóa **không mang danh tính** · fills in only the **non-identity** keys

**VI —** Các khóa sau **KHÔNG BAO GIỜ** thừa kế từ `.env` gốc sang profile: `FAP_PROFILE`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT`, `DISCORD_WEBHOOK_URL`, `DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USER_ID`, `DISCORD_ALLOW_ANYONE`, `GCAL_CALENDAR_ID`, `FAP_ALLOW_UPDATE`. Profile không tự khai ⇒ kênh đó **tắt hẳn** (cố ý: để điểm của người này không bắn vào chat của người kia).
**EN —** These keys are **never** inherited from the root `.env` into a profile: `FAP_PROFILE`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT`, `DISCORD_WEBHOOK_URL`, `DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USER_ID`, `DISCORD_ALLOW_ANYONE`, `GCAL_CALENDAR_ID`, `FAP_ALLOW_UPDATE`. A profile that doesn't declare one has that channel **switched off** — deliberately, so one person's marks never land in another person's chat.

> 🔴 **VI —** `.gitignore` chỉ có dòng `.env` (khớp **đúng** tên đó) ⇒ `.env.alice` **SẼ BỊ COMMIT**. Thêm `.env.*` **và** `!.env.example` vào `.gitignore` **trước khi** tạo profile đầu tiên. Chi tiết: [19-multi-profile](19-multi-profile.md).
> 🔴 **EN —** `.gitignore` only has a bare `.env` (an **exact** name match) ⇒ `.env.alice` **would be committed**. Add `.env.*` **and** `!.env.example` **before** creating your first profile. Details: [19-multi-profile](19-multi-profile.md).

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
| `FAP_REMIND_MINUTES` | `30` | Số **phút** trước mỗi tiết mà **bot tương tác** (`telegram-bot`/`discord-bot`) tự nhắc lịch — mỗi tiết đúng 1 lần, dùng giờ VN. `0` = tắt · minutes before each class the **interactive bot** auto-reminds (once per session, VN time); `0` = off | `FAP_REMIND_MINUTES=15` |
| `FAP_AUTOUPDATE_MIN` | `0` *(tắt)* | **Tự cập nhật khi đang chạy**: số **phút** giữa mỗi lần bot/watcher tự dò `git pull` → `selftest` → nếu PASS thì tự khởi động lại nạp mã mới. `0`/trống = tắt (bot vẫn có lệnh `/update` thủ công — nhưng lệnh đó cần `FAP_ALLOW_UPDATE=1`, xem dòng dưới). · **Update-while-running**: minutes between a resident bot/watcher's auto `git pull` → `selftest` → self-restart on pass; `0` = off (the bots' manual `/update` still exists but now needs `FAP_ALLOW_UPDATE=1`) | `FAP_AUTOUPDATE_MIN=180` |
| `FAP_TOTAL_CREDITS` | `145` | Tổng tín chỉ chương trình cho `fap credits` (FAP không có endpoint CTĐT → đây là **ước lượng**, đặt cho đúng ngành) · total program credits for `fap credits` (an estimate; set it for your major) | `FAP_TOTAL_CREDITS=148` |
| `DISCORD_ALLOW_ANYONE` | *(trống · empty)* | `1` = cho `fap discord-bot` chạy **dù chưa đặt** `DISCORD_ALLOWED_USER_ID` (bot trả lời **MỌI người** — NGUY HIỂM, lộ dữ liệu); trống = bắt buộc có allowlist · `1` lets the Discord bot run without an allowlist (replies to **everyone** — risky); empty = allowlist required | `DISCORD_ALLOW_ANYONE=1` |
| `FAP_PROFILE` | *(trống · empty)* | Tên profile khi chạy **nhiều tài khoản trên 1 máy**: trạng thái vào `output/profiles/<tên>/`, cấu hình đọc `.env.<tên>` trước. Chỉ `A-Z a-z 0-9 . _ -`; tên sai ⇒ bỏ qua (chạy như không có profile). Trống = y hệt trước đây · profile name for **multi-account on one box**: state moves to `output/profiles/<name>/` and `.env.<name>` is read first. Letters/digits/`._-` only; a bad name is ignored. Empty = exactly as before. Xem · see [19-multi-profile](19-multi-profile.md) | `FAP_PROFILE=alice` |
| `FAP_TOKEN_READONLY` | *(trống · empty)* | `1`/`true` = **CẤM `fap refresh` trên máy này**. Dùng cho máy PHỤ dùng chung 1 session (PC copy token từ VPS): `refresh_token` **xoay vòng** nên chỉ **MỘT** máy được refresh. **ĐỪNG đặt trên máy chạy bot/watcher** — token sẽ hết hạn và watcher chết lặng · `1`/`true` **blocks `fap refresh` on this machine**. For the secondary box in a shared session; the `refresh_token` **rotates**, so only **ONE** machine may refresh. **Never set it on the bot/watcher box.** Xem · see [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) | `FAP_TOKEN_READONLY=1` |
| `FAP_ALLOW_UPDATE` | *(trống · empty = CẤM · off)* | `1`/`true` = cho phép lệnh bot **`/update`** (`git pull` + selftest + tự khởi động lại). Mặc định **TẮT** vì `/update` tác động lên **checkout dùng chung của mọi profile**. Chỉ đặt trong unit/`.env` của **chủ máy**; kiểm tra chủ sở hữu bot vẫn chạy trước như cũ · `1`/`true` enables the bot's **`/update`**. **Off by default** because `/update` acts on the **checkout every profile shares**. Owner-only checks still apply | `FAP_ALLOW_UPDATE=1` |

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

# Nhiều tài khoản trên 1 máy — để trống = chế độ 1 tài khoản như cũ
# Multi-account on one box — empty = single-account mode, exactly as before
FAP_PROFILE=

# 1 = CẤM refresh trên máy này (máy PHỤ dùng chung session; ĐỪNG đặt trên máy chạy bot/watcher)
# 1 = block refresh here (secondary box in a shared session; never on the bot/watcher box)
FAP_TOKEN_READONLY=

# 1 = cho phép lệnh bot /update (git pull + tự khởi động lại). Trống = CẤM.
# 1 = allow the bot's /update (git pull + self-restart). Empty = off.
FAP_ALLOW_UPDATE=
```

**VI —** Sau khi sửa `.env`, kiểm tra nhanh bằng `fap doctor` để xem cấu hình đã được nạp đúng chưa.
**EN —** After editing `.env`, sanity-check with `fap doctor` to confirm the config loaded correctly.

> **VI —** Nhắc lại: `.env`, `credentials.json` và toàn bộ thư mục `output/` đều `.gitignore` vì chứa secret/PII.
> **EN —** Reminder: `.env`, `credentials.json`, and the whole `output/` folder are all `.gitignore`d because they hold secrets/PII.
