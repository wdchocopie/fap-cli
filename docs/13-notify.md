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
| `fap notify semester [pattern\|weeks\|list] [<kỳ>]` | vi · gửi lịch **CẢ KỲ**: mẫu lặp hằng tuần (mặc định) / mỗi tuần 1 dòng / liệt kê từng ngày. en · push the **WHOLE TERM**: weekly pattern (default) / one line per week / day-by-day list. |
| `fap notify attendance` | vi · gửi bảng **điểm danh**. en · push the **attendance** table. |
| `fap notify banrisk` | vi · gửi **cảnh báo cấm thi** (môn < 80%). en · push **exam-ban risk** (subjects < 80%). |
| `fap notify grades` · `status` · `whatif [điểm]` | vi · điểm / tổng quan / mô phỏng GPA. en · grades / overview / GPA what-if. |
| `fap notify grades-detail [MÔN]` | vi · điểm thành phần; kèm **mã hoặc tên môn** = chỉ 1 môn (kỳ 6 môn: **8 → 3 request**). en · component marks; naming a subject fetches only that one. |
| `fap notify exams` | vi · gửi **lịch thi** (hẹn lịch để **nhắc trước ngày thi**). en · push the **exam schedule** (schedule it for exam reminders). |

**VI —** Mọi lệnh (trừ `test`) dùng **chung lõi với bot** (`bot_core`) rồi đẩy kết quả lên kênh đã cấu hình. Không đối số → mặc định `test`. Bản không cài đặt: `python -m fapc notify <lệnh>`.
**EN —** Every command (except `test`) shares the **bot core** (`bot_core`) and pushes the result to your configured channels. No argument → defaults to `test`. Non-install: `python -m fapc notify <cmd>`.

> ✅ **VI —** Bảng trên chỉ là những lệnh hay dùng: `notify` nhận **MỌI lệnh của bot** vì allowlist được **sinh từ `COMMAND_INFO`** (thêm lệnh mới là `notify` gửi được ngay, không phải sửa file). Xem danh sách đầy đủ: **`fap notify help`**. Tham số **nhiều từ được giữ nguyên** (`fap notify semester Fall2026 weeks` không còn bị cụt mất chữ `weeks`).
> ✅ **EN —** The table lists the common ones: `notify` accepts **every bot command**, because its allowlist is **derived from `COMMAND_INFO`** (a new command is pushable immediately — no edit needed here). Full list: **`fap notify help`**. Multi-word arguments are **kept intact** (`fap notify semester Fall2026 weeks` no longer loses `weeks`).

```bash
fap notify test         # ping thử · sanity ping
fap notify today        # lịch hôm nay · today's classes
fap notify weekly       # lịch cả tuần · the whole week
fap notify semester     # lịch cả kỳ (mẫu lặp) · the whole term (weekly pattern)
fap notify banrisk      # cảnh báo cấm thi · exam-ban risk
fap notify attendance   # bảng điểm danh · attendance table
fap notify grades-detail IAP491   # điểm thành phần 1 môn · one subject's components
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
   🔗 https://meet.google.com/abc-defg-hij
```

**VI —** Định dạng mỗi dòng: `🕐 HH:MM–HH:MM  <mã môn>  📍 <phòng>`.
- **Học online** (`isOnline`): hiện **`💻 Online`** thay cho phòng, và **link vào lớp `🔗` ở dòng ngay dưới** (chạm là vào Google Meet).
- **Học tại lớp**: hiện **`📍 <số phòng>`** (`roomNo`).
- **Buổi đã qua**: cuối dòng có **`✅`** (có mặt) hoặc **`❌`** (vắng) theo `attendanceStatus`; buổi chưa diễn ra không có dấu.
**EN —** Each line is `🕐 HH:MM–HH:MM  <subjectCode>  📍 <room>`.
- **Online class** (`isOnline`): shows **`💻 Online`** instead of a room, plus the **join link `🔗` on the next line** (tap to open Google Meet).
- **In-person class**: shows **`📍 <room number>`** (`roomNo`).
- **Past sessions** end with **`✅`** (present) or **`❌`** (absent) from `attendanceStatus`; sessions not yet held have no mark.

> 🔗 **VI — Link vào lớp online lấy từ đâu?** FAP trả field `meetURL`, nhưng thực chất là **mã phòng Google Meet trần** (`abc-defg-hij`), không phải URL — fap-cli ghép thành `https://meet.google.com/<mã>`. Mỗi lớp có **một** phòng Meet cố định, nhưng FAP chỉ gắn mã vào **vài buổi** của lớp; buổi online nào thiếu mã sẽ **mượn mã của chính lớp đó** (cùng môn + cùng nhóm, và chỉ khi lớp có đúng một mã — không đoán). Link chỉ hiện ở buổi **online**; buổi học tại phòng không hiện dù có mã. Có mặt ở: nhắc tiết, `/today` `/tomorrow` `/week` `/status` `/all`, `fap notify today|weekly`, `fap status|week`, `semester list`, `week-exact` (chỉ buổi tự mang mã — TKB theo tuần không đủ ngữ cảnh cả kỳ để mượn mã an toàn), file `.ics` và **Google Calendar** (trong mô tả sự kiện — chạy `calendar-sync` một lần để cập nhật sự kiện cũ).
> 🔗 **EN — Where does the online join link come from?** FAP returns a `meetURL` field that is really a **bare Google Meet room code** (`abc-defg-hij`), not a URL — fap-cli builds `https://meet.google.com/<code>`. Each class has **one** fixed Meet room, but FAP attaches the code to only **some** of its sessions; an online session missing it **borrows its own class's code** (same subject + same group, and only when the class has exactly one code — no guessing). The link shows only for **online** sessions. It appears in: class reminders, `/today` `/tomorrow` `/week` `/status` `/all`, `fap notify today|weekly`, `fap status|week`, `semester list`, `week-exact` (only sessions that carry their own code — a single week lacks the whole-term context to borrow safely), the `.ics` file and **Google Calendar** (in the event description — run `calendar-sync` once to update existing events).

**VI —** Hôm đó không có buổi nào:
**EN —** If there are no sessions that day:

```
📅 Thứ 3 · 23/06/2026
━━━━━━━━━━━━━━━━
🎉 Hôm đó không có buổi học
```

> **VI —** Ngôn ngữ tin (vi/en) theo `FAP_LANG` trong `.env` (mặc định `vi`). Ngày "hôm nay/ngày mai" tính theo **giờ VN (Asia/Ho_Chi_Minh)** — cố định trong code, không phải biến `.env`.
> **EN —** Message language (vi/en) follows `FAP_LANG` in `.env` (default `vi`). "Today/tomorrow" is computed in **VN time (Asia/Ho_Chi_Minh)** — hard-coded, not an `.env` key.

> **VI —** Mỗi tin có trần 4000 ký tự (Telegram) / 1900 (Discord) — lịch một ngày luôn nằm dưới mức này. Tin **dài hơn** (vd `/grades-detail`, `/all` nhiều môn) **không còn bị cắt cụt**: nó được **chia thành nhiều tin** gửi liên tiếp (nghỉ ~0.4s giữa các mẩu, ưu tiên cắt ở ranh giới dòng). Nhận 2–3 tin liền nhau là **bình thường**.
> **EN —** Each message is capped at 4000 chars (Telegram) / 1900 (Discord) — one day's digest is always well under. **Longer** replies (e.g. `/grades-detail`, `/all` with many courses) are **no longer truncated**: they are **split across several messages** sent back-to-back (~0.4s apart, cut at line boundaries). Getting 2–3 messages in a row is **expected**.

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

**VI —** Khác với `notify` (đẩy 1 chiều), bot là **tiến trình chạy nền** trả lời lệnh bạn gõ trong chat: `/today`, `/tomorrow`, `/week`, `/weekly`, `/semester`, `/courses`, `/grades`, `/grades-detail [môn]`, `/gpa`, `/gpa-trend`, `/credits`, `/conduct`, `/attendance`, `/banrisk`, `/exams`, `/exam-countdown`, `/whatif [điểm]`, `/status`, `/all`, `/notifications`, `/profile`, `/applications`, `/help`.
**EN —** Unlike `notify` (one-way push), a bot is a **long-running process** that answers commands you type in chat: `/today`, `/tomorrow`, `/week`, `/weekly`, `/semester`, `/courses`, `/grades`, `/grades-detail [subject]`, `/gpa`, `/gpa-trend`, `/credits`, `/conduct`, `/attendance`, `/banrisk`, `/exams`, `/exam-countdown`, `/whatif [mark]`, `/status`, `/all`, `/notifications`, `/profile`, `/applications`, `/help`.

> ✅ **VI —** Danh sách trên là **23/23 lệnh** — đúng bằng `COMMAND_INFO`. Trước đây `/help` và các nút web chép tay nên **sót 6 lệnh** (`weekly`, `courses`, `exam-countdown`, `gpa-trend`, `credits`, `conduct`): chúng chạy được nhưng **không ai thấy**. Nay `/help` + nút web đều **sinh từ `COMMAND_INFO`** (`bot_core.command_groups()`), lệnh chưa xếp nhóm tự rơi vào nhóm **"Lệnh khác"** thay vì biến mất ⇒ **không thể sót nữa**. Bản chuẩn luôn là `/help`.
> ✅ **EN —** That is **23 of 23 commands** — exactly `COMMAND_INFO`. `/help` and the web buttons used to be hand-written lists that **missed 6 commands** (`weekly`, `courses`, `exam-countdown`, `gpa-trend`, `credits`, `conduct`): they worked, but nobody could see them. Both are now **generated from `COMMAND_INFO`** (`bot_core.command_groups()`), and an ungrouped command falls into a trailing **"More"** group instead of disappearing ⇒ **drift is now impossible**. `/help` is always the source of truth.

> 🎓 **VI —** `/semester` gửi lịch **CẢ KỲ** (mặc định = **mẫu lặp hằng tuần** mỗi môn + buổi lệch mẫu; `/semester weeks` = mỗi tuần 1 dòng; `/semester list` = liệt kê từng ngày, tin này **dài** nên sẽ bị chia thành nhiều mẩu). ⚠️ Mẫu đó **suy ra** từ lịch xếp cả kỳ nên **KHÔNG phản ánh buổi huỷ / nghỉ lễ** — ghi chú này in **ngay trong tin**. Nghi ngờ một tuần cụ thể thì dùng **`fap week-exact`** ở CLI (`GetActivityStudentByWeek`, bản server trả cho đúng tuần đó); `week-exact` **không** phải lệnh bot.
> 🎓 **EN —** `/semester` pushes the **whole term** (default = each subject's **repeating weekly slot** + off-pattern sessions; `/semester weeks` = one line per week; `/semester list` = day-by-day, a **long** reply that gets split into several messages). ⚠️ The pattern is **inferred** from the planned term timetable, so it does **NOT reflect cancellations or holidays** — that caveat is printed **inside the message**. For a disputed week use **`fap week-exact`** on the CLI (`GetActivityStudentByWeek`, the server's answer for that exact week); `week-exact` is **not** a bot command.

> 🧮 **VI —** `/grades-detail` kèm **mã hoặc tên môn** (`/grades-detail IAP301`, `/grades-detail iap`) chỉ kéo **1 môn**: kỳ 6 môn từ **8 request xuống 3** — trả lời nhanh hơn nhiều. Khớp nhiều môn → bot **liệt kê ứng viên** để bạn gõ rõ hơn.
> 🧮 **EN —** `/grades-detail` with a **code or name** (`/grades-detail IAP301`, `/grades-detail iap`) fetches **one subject only**: a 6-subject term drops from **8 requests to 3** — a much faster reply. An ambiguous query makes the bot **list the candidates** so you can be more specific.

> ⚠️ **VI —** Lệnh **gõ tay** trong chat (Telegram, và Discord tiền tố `!`) chỉ lấy **từ đầu tiên** làm tham số: `/grades-detail IAP301` ✅, `/semester weeks` ✅, `/semester Fall2026` ✅ — nhưng `/semester Fall2026 weeks` sẽ **mất chữ "weeks"**. Cần tham số nhiều từ thì dùng **slash command của Discord** (`/semester` rồi điền ô `arg`), **ô tham số** trên `fap web`, hoặc CLI/`fap notify` (cả hai giữ nguyên cả cụm).
> ⚠️ **EN —** **Typed** chat commands (Telegram, and Discord's `!` prefix) take only the **first word** as the argument: `/grades-detail IAP301` ✅, `/semester weeks` ✅, `/semester Fall2026` ✅ — but `/semester Fall2026 weeks` **loses "weeks"**. For multi-word arguments use **Discord's slash command** (`/semester` then fill the `arg` field), the **arg box** in `fap web`, or the CLI / `fap notify` (both keep the whole string).

```bash
fap telegram-bot     # bot Telegram (không cần cài thêm · no extra deps)
fap discord-bot      # bot Discord (cần · needs: pip install -e ".[bot]")
```

> 🔒 **VI —** Bot chỉ trả lời **CHỦ tài khoản** để không lộ điểm/dữ liệu cho người lạ. Telegram: chỉ chat `TELEGRAM_CHAT`. Discord: chỉ user `DISCORD_ALLOWED_USER_ID` (nếu để trống → cảnh báo & trả lời mọi người, **nên đặt**).
> 🔒 **EN —** A bot only answers the **account owner** so it never leaks your grades to strangers. Telegram: only chat `TELEGRAM_CHAT`. Discord: only user `DISCORD_ALLOWED_USER_ID` (empty → it warns and replies to everyone, so **set it**).

> 🔑 **VI —** Lệnh **`/update`** (`git pull` + selftest + tự khởi động lại) **TẮT mặc định**: nó tác động lên **checkout dùng chung**, nên ngoài việc phải là chủ bot còn cần `FAP_ALLOW_UPDATE=1` trên máy chạy bot. Xem [15-config](15-config.md) · [19-multi-profile](19-multi-profile.md).
> 🔑 **EN —** The **`/update`** command is **off by default**: it acts on the **shared checkout**, so besides being the bot owner you also need `FAP_ALLOW_UPDATE=1` on the host.

> ⚠️ **VI —** **Đừng chạy CÙNG một `TELEGRAM_TOKEN` ở hai nơi** (vd VPS *và* PC): Telegram trả **409 Conflict**, bot lặp vô hạn và **ngừng trả lời**; nhắc lịch cũng **trùng 100%**. Xem [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines).
> ⚠️ **EN —** **Never run the same `TELEGRAM_TOKEN` in two places** (e.g. VPS *and* PC): Telegram returns **409 Conflict**, the poller spins forever and the bot **stops answering**; reminders also **always double**.

> 📋 **VI —** Bot **tự đăng ký danh sách lệnh gợi ý** lúc khởi động — khỏi nhớ lệnh. Telegram hiện nút **Menu ☰** cạnh ô nhập + tự gợi ý khi gõ `/`. Discord có **slash command** (`/today`, `/grades`, `/whatif`…) hiện ngay khi gõ `/`. Muốn **chạm là chạy** thì gõ `/menu` (Telegram) hoặc `!menu` / `/menu` (Discord) — xem [§8.3](#83-nút-bấm--menu--buttons--menu). Danh sách đầy đủ vẫn là `/help`. Nguồn lệnh: `COMMAND_INFO` trong `fapc/app/bot_core.py` (thêm 1 dòng là cả 2 nền tảng có ngay).
> 📋 **EN —** The bots **auto-register a suggested command list** on startup — no need to memorize. Telegram shows a **Menu ☰** button + autocompletes as you type `/`. Discord exposes **slash commands** (`/today`, `/grades`, `/whatif`…) the moment you type `/`. For **tap-to-run**, send `/menu` (Telegram) or `!menu` / `/menu` (Discord) — see [§8.3](#83-nút-bấm--menu--buttons--menu). Full list is still `/help`. Source of truth: `COMMAND_INFO` in `fapc/app/bot_core.py` (add one line → both platforms get it).

> ⏰ **VI —** **Nhắc trước mỗi tiết:** khi đang chạy, bot **tự đẩy lời nhắc `FAP_REMIND_MINUTES` phút trước giờ vào lớp** (mặc định 30', mỗi tiết đúng 1 lần, theo giờ VN). Telegram nhắc vào chat `TELEGRAM_CHAT`; Discord **DM** cho `DISCORD_ALLOWED_USER_ID`. Đặt `FAP_REMIND_MINUTES=15` để đổi, `0` để tắt. Bot phải **đang chạy** mới nhắc (trên VPS dùng `fap-bot.service` để chạy 24/7). Vòng nhắc cũng **tự `refresh` token ~50'** nên bot không chết token khi chạy dài. Tiết **online** kèm luôn dòng **`🔗 Vào lớp: https://meet.google.com/…`** ở cuối lời nhắc — chạm là vào lớp (xem [§5](#5-nội-dung-tin-nhắn--what-the-digest-looks-like)).
> ⏰ **EN —** **Per-class reminders:** while running, the bot **auto-pushes a reminder `FAP_REMIND_MINUTES` minutes before each class** (default 30, once per session, VN time). Telegram pings `TELEGRAM_CHAT`; Discord **DMs** `DISCORD_ALLOWED_USER_ID`. Set `FAP_REMIND_MINUTES=15` to change, `0` to disable. The bot must be **running** to remind (on a VPS use `fap-bot.service` for 24/7). The reminder loop also **auto-`refresh`es the token ~50m** so a long-running bot won't die on token expiry. **Online** classes get a final **`🔗 Join: https://meet.google.com/…`** line — tap it to join (see [§5](#5-nội-dung-tin-nhắn--what-the-digest-looks-like)).

### 8.1. Telegram bot
**VI —** Dùng lại `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` ở §2 (cả hai **bắt buộc**). Chạy `fap telegram-bot` rồi nhắn `/today` cho bot. Dừng bằng `Ctrl+C`. Long-polling — không cần URL công khai, chạy sau NAT được.
**EN —** Reuses `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` from §2 (both **required**). Run `fap telegram-bot`, then DM the bot `/today`. Stop with `Ctrl+C`. It long-polls — no public URL needed, works behind NAT.

### 8.2. Discord bot
**VI —**
1. [Developer Portal](https://discord.com/developers/applications) → **New Application** → tab **Bot** → **Reset Token** → copy vào `DISCORD_BOT_TOKEN` (token bot, **khác** webhook URL ở §3).
2. Vẫn ở tab **Bot**: bật **MESSAGE CONTENT INTENT** (bắt buộc để bot đọc nội dung lệnh).
3. Tab **OAuth2 → URL Generator**: chọn scope **`bot` + `applications.commands`** (scope thứ 2 cho **slash command** `/`), quyền *Send Messages* → mở URL để mời bot vào server.
4. Lấy **id user của bạn** (bật Developer Mode → chuột phải avatar → Copy User ID) → `DISCORD_ALLOWED_USER_ID`.
5. `pip install -e ".[bot]"` rồi `fap discord-bot`. Gõ **`!`** (`!today`, `!grades`, `!whatif 8`) **hoặc** **slash** `/today` (gõ `/` để hiện gợi ý; lần đầu Discord có thể mất tới ~1h để slash xuất hiện).

**EN —**
1. [Developer Portal](https://discord.com/developers/applications) → **New Application** → **Bot** tab → **Reset Token** → copy into `DISCORD_BOT_TOKEN` (the bot token, **not** the webhook URL from §3).
2. Same **Bot** tab: enable **MESSAGE CONTENT INTENT** (required so the bot can read command text).
3. **OAuth2 → URL Generator**: pick scopes **`bot` + `applications.commands`** (the 2nd scope enables **slash commands** `/`) + *Send Messages* → open the URL to invite the bot to your server.
4. Get **your user id** (enable Developer Mode → right-click your avatar → Copy User ID) → `DISCORD_ALLOWED_USER_ID`.
5. `pip install -e ".[bot]"`, then `fap discord-bot`. Type `!`-prefixed commands (`!today`, `!grades`, `!whatif 8`) **or** **slash** `/today` (type `/` to see suggestions; Discord may take up to ~1h to show new slash commands the first time).

### 8.3. Nút bấm & menu · Buttons & menu

**VI —** Không phải nhớ lệnh nữa: cả hai bot đăng được một **bảng NÚT BẤM** — chạm một cái là chạy lệnh.
**EN —** No more memorising commands: both bots can post a **BUTTON panel** — one tap runs the command.

| | Telegram | Discord |
|---|---|---|
| Gọi bảng nút · Summon it | `/menu` — `/start` và `/help` cũng kèm nút · `/start` and `/help` carry it too | `!menu` **hoặc** slash `/menu` |
| Kiểu nút · Widget | `inline_keyboard` — **12 nút**, **3 nút/hàng** | `discord.ui.View` — tối đa **25 nút** (5×5) |
| Nhãn nút · Label | `/today`, `/grades`… | `today`, `grades`… |
| Nguồn · Source | `bot_core.menu_commands()` → **`COMMAND_INFO`** | `bot_core.menu_commands()` → **`COMMAND_INFO`** |

**VI —** Điểm quan trọng: **không có danh sách chép tay lần hai**. Thêm một dòng vào `COMMAND_INFO` là lệnh đó xuất hiện ở CLI, `/help`, menu gợi ý, slash command, nút web **và** bảng nút — cùng lúc.
**EN —** The key property: there is **no second hand-written list**. Add one line to `COMMAND_INFO` and the command shows up in the CLI, `/help`, the suggestion menu, the slash commands, the web buttons **and** the button panel — all at once.

> 🔒 **VI —** Nút **kiểm quyền y hệt lệnh gõ tay**. Telegram: chạm nút từ chat lạ bị bỏ qua **im lặng** (chỉ ack cho hết quay vòng, không trả lời). Discord: người ngoài bấm nhận lời từ chối **riêng tư** (ephemeral) và lệnh **không** được chạy. **Không có nút `/update`** trên bảng — `update` không nằm trong `COMMAND_INFO`, nên nó vẫn phải gõ tay và vẫn cần `FAP_ALLOW_UPDATE=1`.
> 🔒 **EN —** Buttons enforce **the same owner check as typed commands**. Telegram: a tap from a foreign chat is dropped **silently** (it only acks so the spinner stops). Discord: a stranger gets an **ephemeral** refusal and the command **never runs**. There is **no `/update` button** — `update` is not in `COMMAND_INFO`, so it stays a typed, `FAP_ALLOW_UPDATE=1`-gated command.

> 📱 **VI —** Chi tiết kỹ thuật đáng biết: Telegram gắn bàn phím vào **mẩu CUỐI** khi tin bị chia nhiều mẩu (gắn mẩu đầu thì bàn phím bị đẩy trôi lên khỏi màn hình), và **luôn trả lời `answerCallbackQuery` trước** khi chạy lệnh — nếu không, nút quay vòng ~30 giây trong lúc chờ FAP. Discord **giữ nút sống sau khi bot khởi động lại** (`add_view` lúc `on_ready`), nên bảng `!menu` cũ vẫn bấm được sau `/update`.
> 📱 **EN —** Worth knowing: Telegram attaches the keyboard to the **LAST** chunk of a split message (on the first chunk it would scroll away), and **always answers `answerCallbackQuery` first** — otherwise the button spins for ~30s while FAP replies. Discord **keeps buttons alive across restarts** (`add_view` on `on_ready`), so an old `!menu` panel still works after `/update`.

> 🎨 **VI —** Discord còn gói câu trả lời vào **embed** (dòng tiêu đề thành *title*, phần còn lại thành *description*) cho dễ đọc. Tin quá dài (tiêu đề > 250 hoặc thân > 4000 ký tự) **tự lùi về plain-text chia mẩu ≤1900** — **không bao giờ cắt cụt chữ**; embed gửi hỏng cũng thử lại bằng plain-text.
> 🎨 **EN —** Discord also wraps replies in an **embed** (header line → *title*, the rest → *description*). Anything too big (title > 250 or body > 4000 chars) **falls back to chunked plain text ≤1900** — text is **never truncated** — and a failed embed send is retried as plain text.

> ℹ️ **VI —** Bảng nút chỉ hiện **12 lệnh đầu** (Telegram) / **25** (Discord) theo thứ tự `COMMAND_INFO`. Lệnh dôi ra **vẫn chạy được** — gõ tay hoặc dùng menu gợi ý `/`.
> ℹ️ **EN —** The panel shows the **first 12** (Telegram) / **25** (Discord) commands in `COMMAND_INFO` order. Anything beyond the cap **still works** — type it, or use the `/` suggestion menu.

### 8.4. `/login` — đăng nhập FAP ngay trong chat · sign in from the chat

**VI —** Token FAP hết hạn mà bạn đang ở ngoài? Gõ `/login` **trong Telegram** — không cần SSH vào máy chủ. Lần đầu (chưa có token) thì thêm mã campus: `/login APHL`; các lần sau bot tự lấy campus từ token cũ. Gõ thiếu campus, bot **in luôn danh sách campus** cho bạn chọn.
**EN —** FAP token expired while you're away? Send `/login` **in Telegram** — no SSH needed. On a first-ever login add the campus code (`/login APHL`); afterwards the bot reuses the campus from the old token. Omit it and the bot prints the campus list for you.

> 🔒 **VI — Mật khẩu KHÔNG BAO GIỜ đi qua bot.** Đây là OAuth (FE Identity / Google): bạn đăng nhập trên **trang của Google**, bot không thấy và không lưu mật khẩu.
> 🔒 **EN — Your password never touches the bot.** This is OAuth: you sign in on **Google's own page**; the bot never sees or stores a password.

| Đường · Path | Chat chứa gì · What lands in the chat |
|---|---|
| **Device flow** *(ưu tiên · preferred)* | vi · **chỉ một link**. Mã uỷ quyền không hề đi qua Telegram. Bạn duyệt trên điện thoại, bot tự báo `✅ Đăng nhập xong`. en · a link only; the authorization code never enters the chat. |
| **PKCE** *(dự phòng khi FE Identity từ chối device flow)* | vi · bạn phải **dán URL redirect**. URL đó chứa **mã dùng-một-lần** → bot **xoá tin của bạn ngay khi nhận** (trước cả khi đổi mã); xoá không được thì bot **báo để bạn tự xoá**. en · you paste the redirect URL; the bot deletes that message the moment it arrives, and says so if it cannot. |

**VI —** Chốt an toàn kèm theo:
- **Đăng nhập ra tài khoản KHÁC → từ chối + hoàn tác** cả `token.json` lẫn `oauth_tokens.json`. Chỉ trả lại `token.json` là vô nghĩa: `refresh_token` của người lạ còn nằm đó thì lần refresh sau sẽ dựng lại token của họ. Không đọc được `rollNumber` cũng bị coi là **khác** — không định danh được thì không tin.
- Máy đặt `FAP_TOKEN_READONLY=1` (xem [14-deploy §9](14-deploy.md)) **bị cấm** `/login`: đăng nhập ở đó sẽ vô hiệu hoá token của máy chủ.
- Token **không bao giờ** được in ra chat — chỉ báo `rollNumber` + campus.
- Chỉ chủ chat (`TELEGRAM_CHAT`) gọi được, y như mọi lệnh khác.

**EN —** Guards: a sign-in that yields a **different account** (or no readable roll number) is refused and **both** token files are rolled back; a host with `FAP_TOKEN_READONLY=1` may not `/login`; tokens are never printed to chat; owner-chat only.

> ⚠️ **VI —** Hiện chỉ có trên **Telegram** (Discord chưa hỗ trợ — dùng `fap login` trên máy chủ).
> ⚠️ **EN —** Telegram only for now (on Discord use `fap login` on the host).

### 8.5. `.env` cho bot · for the bot
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
