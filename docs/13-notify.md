# Thông báo Telegram & Discord · Telegram & Discord notifications

**VI —** Lệnh `fap notify` đẩy **lịch học, điểm danh, điểm, tổng quan...** (xem §1) lên Telegram và/hoặc Discord. Hai kênh hoàn toàn độc lập: bật một, cả hai, hoặc không kênh nào. Tất cả cấu hình nằm trong `.env` ở gốc repo.
**EN —** The `fap notify` command pushes your **schedule, attendance, grades, overview...** (see §1) to Telegram and/or Discord. The two channels are fully independent: enable one, both, or neither. All config lives in `.env` at the repo root.

> **VI —** Biến kênh để trống = kênh đó bị **bỏ qua âm thầm** (không lỗi, không gửi). Không có kênh nào cấu hình thì lệnh vẫn chạy và chỉ in lịch ra màn hình.
> **EN —** An empty channel var means that channel is **silently skipped** (no error, no send). With no channel configured the command still runs and just prints the digest to the console.

---

## 1. Các lệnh · The commands

| Lệnh · Command | Tác dụng · What it does |
|---|---|
| `fap notify test` | vi · gửi tin nhắn thử "kênh hoạt động" tới mọi kênh đã cấu hình — kiểm tra dây nối. en · send a "channels work" sanity ping to every configured channel. |
| `fap notify today` | vi · gửi lịch **HÔM NAY** (theo giờ VN). en · push **TODAY's** schedule (VN time). |
| `fap notify tomorrow` | vi · gửi lịch **NGÀY MAI**. en · push **TOMORROW's** schedule. |
| `fap notify weekly` | vi · gửi lịch **CẢ TUẦN** (T2–CN). en · push the **WHOLE WEEK** (Mon–Sun). |
| `fap notify attendance` | vi · gửi bảng **điểm danh**. en · push the **attendance** table. |
| `fap notify banrisk` | vi · gửi **cảnh báo cấm thi** (môn < 80%). en · push **exam-ban risk** (subjects < 80%). |
| `fap notify grades` · `status` · `whatif [điểm]` | vi · điểm / tổng quan / mô phỏng GPA. en · grades / overview / GPA what-if. |
| `fap notify exams` | vi · gửi **lịch thi** (hẹn lịch để **nhắc trước ngày thi**). en · push the **exam schedule** (schedule it for exam reminders). |

**VI —** Mọi lệnh (trừ `test`) dùng **chung lõi với bot** (`bot_core`) rồi đẩy kết quả lên kênh đã cấu hình. Không đối số → mặc định `test`. Bản không cài đặt: `python -m fapc notify <lệnh>`.
**EN —** Every command (except `test`) shares the **bot core** (`bot_core`) and pushes the result to your configured channels. No argument → defaults to `test`. Non-install: `python -m fapc notify <cmd>`.

```bash
fap notify test         # ping thử · sanity ping
fap notify today        # lịch hôm nay · today's classes
fap notify weekly       # lịch cả tuần · the whole week
fap notify banrisk      # cảnh báo cấm thi · exam-ban risk
fap notify attendance   # bảng điểm danh · attendance table
```

> **VI —** `today`/`tomorrow` cần token FAP còn hạn (chạy `fap login` rồi `fap refresh`). `test` thì không cần token — chỉ thử kênh chat.
> **EN —** `today`/`tomorrow` need a valid FAP token (run `fap login`, then `fap refresh`). `test` needs no token — it only exercises the chat channels.

---

## 2. Telegram

### 2.1. Tạo bot & lấy token · Create a bot & get the token

**VI —**
1. Mở Telegram, nhắn cho **@BotFather**.
2. Gửi `/newbot`, đặt tên và username cho bot.
3. BotFather trả về **HTTP API token** dạng `1234567890:AAEx...` → đây là `TELEGRAM_TOKEN`.

**EN —**
1. Open Telegram, DM **@BotFather**.
2. Send `/newbot`, choose a name and username.
3. BotFather replies with an **HTTP API token** like `1234567890:AAEx...` → that's your `TELEGRAM_TOKEN`.

### 2.2. Lấy chat id · Get your chat id

**VI —** Bot chỉ nhắn được cho bạn sau khi **bạn nhắn cho bot trước**. Hai cách lấy `TELEGRAM_CHAT`:
- Nhắn bất kỳ cho bot, rồi mở trong trình duyệt:
  `https://api.telegram.org/bot<token>/getUpdates`
  Đọc `result[].message.chat.id` — đó là chat id của bạn.
- Hoặc nhắn cho **@userinfobot**, nó trả về id luôn.

**EN —** The bot can only message you **after you message it first**. Two ways to get `TELEGRAM_CHAT`:
- DM the bot anything, then open in a browser:
  `https://api.telegram.org/bot<token>/getUpdates`
  Read `result[].message.chat.id` — that's your chat id.
- Or DM **@userinfobot**, which replies with your id.

> **VI —** Thay `<token>` bằng token thật. Nếu `getUpdates` trả mảng rỗng, hãy nhắn cho bot một lần nữa rồi tải lại trang.
> **EN —** Replace `<token>` with the real token. If `getUpdates` returns an empty array, message the bot once more and reload the page.

---

## 3. Discord

**VI —**
1. Vào **Server Settings → Integrations → Webhooks**.
2. Bấm **New Webhook**, chọn kênh muốn nhận tin.
3. Bấm **Copy Webhook URL** → đây là `DISCORD_WEBHOOK_URL`.

**EN —**
1. Go to **Server Settings → Integrations → Webhooks**.
2. Click **New Webhook**, pick the target channel.
3. Click **Copy Webhook URL** → that's your `DISCORD_WEBHOOK_URL`.

> **VI —** Webhook không cần bot, không cần token bot. Ai có URL là gửi được tin vào kênh đó — đừng để lộ.
> **EN —** A webhook needs no bot and no bot token. Anyone with the URL can post to that channel — keep it secret.

---

## 4. Điền vào `.env` · Fill in `.env`

**VI —** Mở `.env` ở gốc repo (copy từ `.env.example` nếu chưa có) và điền đúng các dòng sau:
**EN —** Open `.env` at the repo root (copy from `.env.example` if missing) and fill in exactly these lines:

```dotenv
# Telegram (BotFather → TOKEN; CHAT = chat id của bạn)
TELEGRAM_TOKEN=1234567890:AAEx-your-bot-token
TELEGRAM_CHAT=123456789

# Discord (Server Settings → Integrations → Webhooks → Copy URL)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/000000/your-webhook-token
```

**VI —** Chỉ dùng Telegram? Để trống `DISCORD_WEBHOOK_URL`. Chỉ dùng Discord? Để trống cả `TELEGRAM_TOKEN` lẫn `TELEGRAM_CHAT`. Kênh để trống sẽ bị bỏ qua âm thầm.
**EN —** Telegram only? Leave `DISCORD_WEBHOOK_URL` empty. Discord only? Leave both `TELEGRAM_TOKEN` and `TELEGRAM_CHAT` empty. An empty channel is silently skipped.

> **VI —** Telegram chỉ bật khi **cả** `TELEGRAM_TOKEN` **và** `TELEGRAM_CHAT` đều có giá trị; thiếu một trong hai = tắt Telegram.
> **EN —** Telegram fires only when **both** `TELEGRAM_TOKEN` **and** `TELEGRAM_CHAT` are set; missing either one disables Telegram.

> **VI —** `.env` đã nằm trong `.gitignore` (chứa bí mật). Đừng commit nó.
> **EN —** `.env` is already in `.gitignore` (it holds secrets). Never commit it.

---

## 5. Nội dung tin nhắn · What the digest looks like

**VI —** Tiêu đề (thứ · ngày · số buổi) + đường kẻ, rồi mỗi buổi một dòng theo giờ:
**EN —** A header (weekday · date · count) + a rule, then one line per session by time:

```
📅 Thứ 3 · 23/06/2026  ·  2 buổi
━━━━━━━━━━━━━━━━
🕐 07:30–09:50  SWP391  📍 AL-R201
🕐 12:30–14:50  PRN231  💻 Online
```

**VI —** Định dạng mỗi dòng: `🕐 HH:MM–HH:MM  <mã môn>  📍 <phòng>`.
- **Học online** (`isOnline`): hiện **`💻 Online`** thay cho phòng.
- **Học tại lớp**: hiện **`📍 <số phòng>`** (`roomNo`).
**EN —** Each line is `🕐 HH:MM–HH:MM  <subjectCode>  📍 <room>`.
- **Online class** (`isOnline`): shows **`💻 Online`** instead of a room.
- **In-person class**: shows **`📍 <room number>`** (`roomNo`).

**VI —** Hôm đó không có buổi nào:
**EN —** If there are no sessions that day:

```
📅 Thứ 3 · 23/06/2026
━━━━━━━━━━━━━━━━
🎉 Hôm đó không có buổi học
```

> **VI —** Ngôn ngữ tin (vi/en) theo `FAP_LANG` trong `.env` (mặc định `vi`). Ngày "hôm nay/ngày mai" tính theo **giờ VN (Asia/Ho_Chi_Minh)** — cố định trong code, không phải biến `.env`.
> **EN —** Message language (vi/en) follows `FAP_LANG` in `.env` (default `vi`). "Today/tomorrow" is computed in **VN time (Asia/Ho_Chi_Minh)** — hard-coded, not an `.env` key.

> **VI —** Telegram cắt ở 4000 ký tự, Discord ở 1900 ký tự mỗi tin — lịch một ngày luôn nằm dưới mức này.
> **EN —** Telegram caps at 4000 chars, Discord at 1900 chars per message — a single day's digest is always well under.

---

## 6. Kiểm tra & xử lý lỗi · Verify & troubleshoot

**VI —** Chạy `fap notify test` trước. Lệnh in danh sách kênh đã gửi:
**EN —** Run `fap notify test` first. It prints the channels it sent to:

```
Đã gửi tới: ['Telegram', 'Discord']
```

**VI —** Nếu in `(chưa cấu hình kênh nào — sửa .env)` thì cả hai biến kênh đang trống — kiểm tra lại `.env`.
**EN —** If it prints `(no channel configured — edit .env)`, both channel vars are empty — recheck `.env`.

| Triệu chứng · Symptom | Nguyên nhân · Likely cause |
|---|---|
| `Telegram lỗi: ...` | vi · token sai, hoặc chưa nhắn cho bot trước, hoặc chat id sai. en · wrong token, you never DM'd the bot, or wrong chat id. |
| `Discord lỗi: ...` | vi · webhook URL sai hoặc đã bị xoá. en · webhook URL wrong or deleted. |
| Gửi `test` được, `today` báo lỗi token | vi · chưa đăng nhập FAP — chạy `fap login` rồi `fap refresh`. en · not logged in to FAP — run `fap login`, then `fap refresh`. |
| Tiếng Việt/emoji bị vỡ trên console Windows | vi · chạy `chcp 65001` hoặc đặt `PYTHONUTF8=1`. en · run `chcp 65001` or set `PYTHONUTF8=1`. |

> **VI —** Tin nhắn vỡ font chỉ ảnh hưởng **bản in ra console**; nội dung gửi lên Telegram/Discord vẫn đúng UTF-8.
> **EN —** A garbled console only affects the **printed copy**; what reaches Telegram/Discord is still correct UTF-8.

---

## 7. Tự động hoá (gợi ý) · Automation (suggested)

**VI —** Muốn nhận lịch mỗi sáng? Hẹn `fap notify today` chạy lúc 6:00 bằng Task Scheduler (Windows) hoặc `cron` (Linux/macOS). Nhớ chạy `fap refresh` trước để token còn hạn. Script sẵn dùng: [docs/14-deploy.md](14-deploy.md) + thư mục [`deploy/`](../deploy/).
**EN —** Want a morning digest? Schedule `fap notify today` at 06:00 via Task Scheduler (Windows) or `cron` (Linux/macOS). Run `fap refresh` first so the token stays valid. Ready scripts: [docs/14-deploy.md](14-deploy.md) + the [`deploy/`](../deploy/) folder.

---

## 8. Bot tương tác · Interactive bots

**VI —** Khác với `notify` (đẩy 1 chiều), bot là **tiến trình chạy nền** trả lời lệnh bạn gõ trong chat: `/today`, `/tomorrow`, `/week`, `/grades`, `/attendance`, `/banrisk`, `/whatif [điểm]`, `/status`, `/help`.
**EN —** Unlike `notify` (one-way push), a bot is a **long-running process** that answers commands you type in chat: `/today`, `/tomorrow`, `/week`, `/grades`, `/attendance`, `/banrisk`, `/whatif [mark]`, `/status`, `/help`.

```bash
fap telegram-bot     # bot Telegram (không cần cài thêm · no extra deps)
fap discord-bot      # bot Discord (cần · needs: pip install -e ".[bot]")
```

> 🔒 **VI —** Bot chỉ trả lời **CHỦ tài khoản** để không lộ điểm/dữ liệu cho người lạ. Telegram: chỉ chat `TELEGRAM_CHAT`. Discord: chỉ user `DISCORD_ALLOWED_USER_ID` (nếu để trống → cảnh báo & trả lời mọi người, **nên đặt**).
> 🔒 **EN —** A bot only answers the **account owner** so it never leaks your grades to strangers. Telegram: only chat `TELEGRAM_CHAT`. Discord: only user `DISCORD_ALLOWED_USER_ID` (empty → it warns and replies to everyone, so **set it**).

### 8.1. Telegram bot
**VI —** Dùng lại `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` ở §2 (cả hai **bắt buộc**). Chạy `fap telegram-bot` rồi nhắn `/today` cho bot. Dừng bằng `Ctrl+C`. Long-polling — không cần URL công khai, chạy sau NAT được.
**EN —** Reuses `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` from §2 (both **required**). Run `fap telegram-bot`, then DM the bot `/today`. Stop with `Ctrl+C`. It long-polls — no public URL needed, works behind NAT.

### 8.2. Discord bot
**VI —**
1. [Developer Portal](https://discord.com/developers/applications) → **New Application** → tab **Bot** → **Reset Token** → copy vào `DISCORD_BOT_TOKEN` (token bot, **khác** webhook URL ở §3).
2. Vẫn ở tab **Bot**: bật **MESSAGE CONTENT INTENT** (bắt buộc để bot đọc nội dung lệnh).
3. Tab **OAuth2 → URL Generator**: chọn scope `bot`, quyền *Send Messages* → mở URL để mời bot vào server.
4. Lấy **id user của bạn** (bật Developer Mode → chuột phải avatar → Copy User ID) → `DISCORD_ALLOWED_USER_ID`.
5. `pip install -e ".[bot]"` rồi `fap discord-bot`. Gõ lệnh prefix **`!`** trong kênh: `!today`, `!grades`, `!whatif 8`.

**EN —**
1. [Developer Portal](https://discord.com/developers/applications) → **New Application** → **Bot** tab → **Reset Token** → copy into `DISCORD_BOT_TOKEN` (the bot token, **not** the webhook URL from §3).
2. Same **Bot** tab: enable **MESSAGE CONTENT INTENT** (required so the bot can read command text).
3. **OAuth2 → URL Generator**: pick scope `bot` + *Send Messages* → open the URL to invite the bot to your server.
4. Get **your user id** (enable Developer Mode → right-click your avatar → Copy User ID) → `DISCORD_ALLOWED_USER_ID`.
5. `pip install -e ".[bot]"`, then `fap discord-bot`. Type `!`-prefixed commands in a channel: `!today`, `!grades`, `!whatif 8`.

### 8.3. `.env` cho bot · for the bot
```dotenv
# Telegram bot: dùng lại TOKEN + CHAT ở §2 (CHAT bắt buộc) · reuses §2 (CHAT required)
# Discord bot:
DISCORD_BOT_TOKEN=your-bot-token            # ≠ DISCORD_WEBHOOK_URL
DISCORD_ALLOWED_USER_ID=123456789012345678  # id user của bạn · your user id
```

> **VI —** Bot gọi API FAP **mỗi lệnh** → cần token FAP còn hạn (`fap login`/`fap refresh`). Lên lịch chạy nền bot: xem [deploy](../deploy/) (chạy như tiến trình thường trú).
> **EN —** The bot hits the FAP API **per command** → needs a valid FAP token (`fap login`/`fap refresh`). To keep a bot running, see [deploy](../deploy/) (run it as a resident process).

---

## 9. Báo điểm danh "tại thời điểm điểm danh" · Near-real-time attendance alerts

**VI —** `fap watch-attendance` báo **ngay khi một buổi vừa được giảng viên điểm danh**.
**EN —** `fap watch-attendance` pings you **the moment a session's attendance is recorded**.

> ⚠️ **VI —** KHÔNG có "tức thì thật": FAP không đẩy (webhook) cho bên thứ ba. Công cụ **dò định kỳ** rồi phát hiện thay đổi `attendanceStatus: Future → Present/Absent` (khoá theo `scheduleID`). Độ trễ ≈ chu kỳ dò, và còn phụ thuộc giảng viên nhập sớm/muộn.
> ⚠️ **EN —** No true real-time: FAP has no third-party push. The tool **polls** and detects the `attendanceStatus: Future → Present/Absent` change (keyed by `scheduleID`). Latency ≈ the poll interval, and depends on how promptly the lecturer enters it.

```bash
fap watch-attendance            # 1 lần: dò -> báo buổi mới -> thoát (cho cron)
fap watch-attendance loop       # chạy nền, dò mỗi 15 phút (06:00–21:00 giờ VN)
fap watch-attendance loop 10    # ... mỗi 10 phút (tối thiểu 5)
fap watch-attendance --absent-only         # CHỈ báo buổi VẮNG/MUỘN (đỡ spam)
fap watch-attendance loop 15 --absent-only
```

### 9.1. Chống lặp / "quá nhiều thông báo" · Anti-spam
**VI —**
- **Mỗi buổi báo ĐÚNG 1 LẦN** — nhớ trong `output/attendance_state.json` (theo `scheduleID`); dò lại **không** báo lại.
- **Im lặng khi không có gì mới** — chỉ gửi khi thật sự có buổi mới được điểm danh.
- **Gộp** — nhiều buổi mới trong 1 lượt → **1 tin** (không phải nhiều tin rời).
- **Chỉ-báo-vắng** — cờ `--absent-only` (hoặc `FAP_WATCH_ABSENT_ONLY=1` trong `.env`): bỏ qua buổi "Có mặt ✅" (bạn vốn biết mình có đi), **chỉ ping khi bị VẮNG/MUỘN** — đúng cái cần biết. Console vẫn hiện đủ; chỉ lọc tin gửi lên kênh.

**EN —**
- **Each session pings exactly ONCE** — remembered in `output/attendance_state.json` (by `scheduleID`); re-polls don't re-ping.
- **Silent when nothing changed** — it only sends on a genuinely new record.
- **Batched** — several new records in one round → **one message**.
- **Absent-only** — flag `--absent-only` (or `FAP_WATCH_ABSENT_ONLY=1` in `.env`): skip "Present ✅" records and **only ping on Absent/Late** — what you actually need. Console still logs all; only the chat push is filtered.

**VI —** Nhẹ với server: mỗi lượt chỉ gọi `GetStudentAttendances` (1 lời gọi); chỉ tải chi tiết `getCourseAttendance` cho môn có **số buổi tăng**. Lần chạy đầu chỉ **ghi nhận mốc** (không báo dồn lịch sử). Mốc lưu `output/attendance_state.json`.
**EN —** Server-friendly: each round calls `GetStudentAttendances` once; it only fetches `getCourseAttendance` detail for a subject whose **taken-count rose**. The first run just **records a baseline** (no history spam). State in `output/attendance_state.json`.

**VI —** Chạy nền 24/7: dùng [`deploy/fap-watch.service`](../deploy/fap-watch.service) (systemd, auto-restart) — cặp với refresh token hằng ngày ([`fap.timer`](../deploy/fap.timer)). Hoặc cron mỗi 15' trong giờ học ([`deploy/crontab.example`](../deploy/crontab.example)).
**EN —** Keep it running: [`deploy/fap-watch.service`](../deploy/fap-watch.service) (systemd, auto-restart), paired with the daily token refresh ([`fap.timer`](../deploy/fap.timer)). Or a 15-min cron during class hours ([`deploy/crontab.example`](../deploy/crontab.example)).

**VI —** Tin báo đẩy qua **cùng kênh** Telegram/Discord ở trên. Mẫu · **EN —** Alerts go to the **same** channels. Sample:

```
🔔 Vừa điểm danh!
━━━━━━━━━━━━━━━━
• EXE101 · 22/06/2026 · slot 2
   📍 BE-213 → Có mặt ✅
```
