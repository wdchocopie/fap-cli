# Tham chiếu lệnh `fap` · `fap` command reference

**VI —** Toàn bộ lệnh của fap-cli. Lệnh chuẩn là `fap <command>`; nếu chưa cài gói, dùng dạng tương đương `python -m fapc <command>`.
**EN —** The complete command set of fap-cli. The canonical form is `fap <command>`; if the package is not installed, use the equivalent `python -m fapc <command>`.

> **VI —** Cài đặt: `pip install -e .` ở thư mục gốc repo (tạo lệnh `fap`). Muốn dùng Google Calendar: `pip install -e ".[gcal]"`. Chỉ thao tác trên **TÀI KHOẢN CỦA CHÍNH BẠN**.
> **EN —** Install: `pip install -e .` from the repo root (creates the `fap` command). For Google Calendar: `pip install -e ".[gcal]"`. Use it for **YOUR OWN ACCOUNT** only.

> **VI —** Gọi `fap` không kèm lệnh (hoặc lệnh **thật sự** lạ) sẽ in bảng trợ giúp song ngữ. Nếu tiếng Việt/emoji bị vỡ trên console Windows, chạy `chcp 65001` hoặc đặt `PYTHONUTF8=1`.
> **EN —** Running `fap` with no command (or a **genuinely** unknown one) prints the bilingual help. If Vietnamese/emoji is garbled on the Windows console, run `chcp 65001` or set `PYTHONUTF8=1`.

> ✅ **VI — Mọi lệnh của bot đều CHẠY được từ CLI.** Trước đây `fap today` / `fap tomorrow` in nhầm trang HELP vì không có nhánh CLI riêng. Nay CLI có **nhánh dự phòng chung**: lệnh nào nằm trong `bot_core.COMMAND_INFO` mà chưa có bản CLI riêng sẽ chạy thẳng qua lõi bot (`fapc/app/cli.py` → `_core_cmd()` → `bot_core.handle(cmd, tham_số)`) và **giữ nguyên cụm tham số nhiều từ**. Thêm lệnh mới vào `COMMAND_INFO` là CLI/bot/web/notify có ngay — không bao giờ lệch nữa. Riêng `fap help` (và `fap` trống) vẫn in **trang HELP của CLI**, không phải `/help` của bot.
> ✅ **EN — Every bot command now RUNS from the CLI.** `fap today` / `fap tomorrow` used to print the HELP page because they had no CLI branch. The CLI now has a **generic fallback**: any command in `bot_core.COMMAND_INFO` without a dedicated CLI branch is executed through the bot core (`fapc/app/cli.py` → `_core_cmd()` → `bot_core.handle(cmd, arg)`), **keeping multi-word arguments intact**. Add a command to `COMMAND_INFO` and CLI/bot/web/notify all get it — no more drift. `fap help` (and bare `fap`) still prints the **CLI HELP page**, not the bot's `/help`.

---

## 1. Bảng lệnh · Command table

### Đăng nhập · Auth

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap login` | đăng nhập Google @fpt.edu.vn 1 lần (mở trình duyệt), rồi đổi sang token FAP · one-time Google login (opens browser), then exchange for FAP token | *(không · none)* — hỏi `CampusCode` ở prompt · prompts for `CampusCode` | `output/oauth_tokens.json`, `output/token.json`, `output/.pkce_state.json` (tạm · transient) |
| `fap exchange "<url>"` | đổi URL redirect đã copy thành token (khi không dán lúc `login`) · exchange the copied redirect URL for a token | `"<url>"` = URL `io.identityserver.demo:/oauthredirect?code=...` (bắt buộc · required) | `output/oauth_tokens.json`, `output/token.json` |
| `fap refresh` | làm mới token không cần trình duyệt qua `refresh_token` · renew token headlessly via `refresh_token` | *(không · none)* — đọc campus từ `token.json`, nếu thiếu thì hỏi · reads campus from `token.json`, else prompts | cập nhật · updates `output/oauth_tokens.json`, `output/token.json` |
| `fap fap [campus]` | đổi `access_token` đã lưu sang token FAP (khi riêng bước FAP lỗi) · convert the saved `access_token` to a FAP token (when only the FAP step failed) | `[campus]` tùy chọn · optional; thiếu thì hỏi `CampusCode` · else prompts | cập nhật · updates `output/token.json` |
| `fap whoami [--full] [--json]` | **thẻ định danh OFFLINE**: decode JWT trong `oauth_tokens.json` (KHÔNG gọi mạng) → tài khoản/email/campus/vai trò + **đếm ngược hết hạn** token. `--full` hiện CCCD/SĐT, `--json` cho script · offline identity card from the JWT + expiry countdown | `--full` · `--json` | stdout |
| `fap campuses` | liệt kê `campusCode` đang hoạt động (`GetAllActiveCampus`) — **chạy được TRƯỚC khi login** để biết campus cần nhập · list active campus codes (no login needed) | *(không · none)* | stdout |

### Tổng quan · Overview

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap status` *(alias: `fap dashboard`)* | tổng quan 1 màn hình: lịch hôm nay + GPA tạm tính + điểm danh + cảnh báo cấm thi · one-screen overview: today's classes + provisional GPA + attendance + ban warning | *(không · none)* | stdout |
| `fap all` | **MỌI mục trong 1 lần**: hôm nay → tuần → điểm → điểm thành phần → điểm danh → cấm thi → lịch thi · everything at once | *(không · none)* | stdout |
| `fap today` · `fap tomorrow` | lịch **HÔM NAY** / **NGÀY MAI** (giờ VN), cùng bản tóm tắt mà bot/notify gửi · today's / tomorrow's schedule (VN time), same digest the bot pushes | *(không · none)* | stdout |
| `fap weekly` | **tổng kết tuần** trong 1 tin: lịch tuần + điểm danh + nguy cơ cấm thi + điểm (gửi kênh đã cấu hình) · weekly recap in one message → channels | *(không · none)* | tin nhắn kênh + stdout |
| `fap week [next\|prev\|N]` | lịch cả tuần T2–CN (lọc từ dữ liệu kỳ), tiêu đề kèm **`· Tuần N/M`** khi tra được mốc kỳ · whole-week schedule (Mon–Sun), header carries `· Week N/M` when term bounds resolve | `next`/`sau` = tuần sau, `prev`/`trước` = tuần trước, hoặc số tuần lệch `N` · or integer offset `N` (mặc định · default = tuần này · this week) | stdout |
| `fap week-exact [week year]` | TKB lấy **thẳng từ server** (`GetActivityStudentByWeek`) — chuẩn cho tuần nghỉ lễ/đặc biệt; tự dò số tuần FAP qua `GetWeekByDate` · weekly straight from server | `[week year]` tuỳ chọn; thiếu = tự dò tuần hiện tại · optional, else auto-detect current week | stdout |
| `fap semester [pattern\|weeks\|list] [<tên kỳ>]` | **lịch CẢ KỲ** trong 1 màn hình: `pattern` (mặc định) = **mẫu lặp hằng tuần** mỗi môn + buổi lệch mẫu; `weeks` = mỗi tuần 1 dòng (Tuần N · khoảng ngày · môn nào mấy buổi); `list` = liệt kê từng ngày · whole-term schedule: repeating weekly pattern (default) / one line per week / day-by-day list | `pattern`\|`weeks`\|`list` và/hoặc **tên kỳ khác** (vd `Fall2026`) — gõ thứ tự nào cũng được · view word and/or another term name, in either order | stdout |

### Dữ liệu · Data

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap extract` | kéo toàn bộ endpoint chỉ-đọc về đĩa, kèm chi tiết điểm danh từng môn · pull every read-only endpoint to disk, plus per-subject attendance | *(không · none)* | `output/api/<endpoint>.json`, `output/api/courseAttendance__<mã>.json` |
| `fap ics` *(alias: `fap run`)* | xuất thời khóa biểu ra file `.ics` để import Calendar · export the timetable to an `.ics` file for Calendar import | *(không · none)* | `output/lichhoc.ics` + tóm tắt stdout |
| `fap grades` | bảng điểm tổng kết môn + **tên môn** + GPA tạm tính (**theo tín chỉ** nếu đã `fap subjects`) · subject summary + names + provisional GPA (credit-weighted when the catalog is cached) | *(không · none)* | stdout |
| `fap grades-detail [MÔN] [--raw]` | điểm thành phần từng môn + dòng **"cần X/10 ở phần còn lại để qua"**. Hợp nhất `GetStudentMark` với **`GetCourseOfSemester`** → môn bị bỏ sót / thiếu `courseID` vẫn lấy được điểm thành phần. Kèm **mã hoặc tên môn** = chỉ kéo **1 môn** (kỳ 6 môn: **8 → 3 request**) · component grades + pass-projection; pass a subject code/name to fetch just that one | `[MÔN]` = mã (`IAP301`, `iap`) hoặc **một phần tên môn**; `--raw` = in nguyên response `GetMarkByCourse` (chẩn đoán) | stdout |
| `fap subjects` | tải & cache **danh mục môn** (`GetSubjets`) → từ đó **TÊN môn + tín chỉ** hiện ở grades/điểm danh/lịch/bot/web · cache the subject catalog → names + credits everywhere | *(không · none)* | `output/subjects_catalog.json` + stdout |
| `fap courses` | **lớp đang học** trong kỳ: môn / lớp / **giảng viên** / phòng (`GetCourseOfSemester`; fallback gộp từ `GetActivityStudent` nếu lỗi) · my classes this term (subject/class/lecturer/room) | *(không · none)* | stdout |
| `fap attendance` | điểm danh theo môn (% · x/y) + **giai đoạn môn** (chưa bắt đầu / còn N ngày / đã kết thúc) + **ngày vắng** · attendance per subject + term phase + absence dates | *(không · none)* | stdout |
| `fap banrisk` | liệt kê môn nguy cơ cấm thi (proxy chuyên cần < 80%) · list exam-ban-risk subjects (attendance < 80% proxy) | *(không · none)* | stdout + **exit code 2** nếu có nguy cơ · if at risk |
| `fap transcript` | bảng điểm tích lũy; rỗng nếu chưa hoàn tất kỳ nào · academic transcript; empty if no completed semester | *(không · none)* | stdout |
| `fap gpa` | GPA tích lũy **theo tín chỉ** (toàn khoá + từng kỳ) từ `AcademicTranscript`; khác `whatif` (TB cộng kỳ hiện tại) · credit-weighted cumulative GPA | *(không · none)* | stdout |
| `fap gpa-trend` | **GPA mỗi kỳ + xu hướng**: delta so kỳ trước (▲/▼) + sparkline + GPA toàn khoá (sắp xếp kỳ theo thời gian) · per-term GPA trend with deltas + a unicode sparkline | *(không · none)* | stdout |
| `fap credits` | **tiến độ tín chỉ tới tốt nghiệp**: đã đạt / tổng + % + thanh + ước lượng số kỳ còn lại (tổng = `FAP_TOTAL_CREDITS`, mặc định ~145, *ước lượng*) · credit progress to graduation | *(không · none)* | stdout |
| `fap conduct` | **điểm rèn luyện/phong trào** (`GetDiemphongtrao`, xét tốt nghiệp). Server trả `201`/null khi chưa có dữ liệu → hiện "chưa có", không lỗi · conduct / movement points; degrades to "none yet" on the server's empty-data error | *(không · none)* | stdout |
| `fap whatif [target]` | mô phỏng GPA: bảng dự kiến nếu các môn còn lại đạt 5–10, hoặc cần TB bao nhiêu để đạt `target` · GPA what-if: projection table, or the average needed to hit `target` | `[target]` số 0–10 tùy chọn · optional 0–10 number | stdout |
| `fap exams` | lịch thi (`GetScheduleExam`); rỗng nếu trường chưa xếp · exam schedule; empty until scheduled | *(không · none)* | stdout |
| `fap exam-countdown` | **đếm ngược ngày thi**: bỏ kỳ đã qua, sớm nhất trước, nhãn độ gấp (🔴 hôm nay / 🟠 mai / còn N ngày) · days until each upcoming exam, urgency-tagged | *(không · none)* | stdout |
| `fap exams-ics` | xuất lịch thi ra `.ics` (kèm nhắc trước 1 ngày) để import Calendar · export exams to `.ics` (1-day reminder) | *(không · none)* | `output/lichthi.ics` |
| `fap news [từ khoá] [--type=N]` | tin tức: không tham số → `GetTop10News`; có **từ khoá** → **`SearchNews`** (vd `fap news học bổng`); `--type=N` đổi nhóm tin · school news; keyword → SearchNews | `[từ khoá]` · `--type=N` | stdout |
| `fap fees` | số dư + chi tiết học phí (`GetBalance`/`GeFeeByRoll`) · balance + fee details | *(không · none)* | stdout |
| `fap notifications [#id\|từ khoá]` | thông báo cá nhân (`GetNotificationByRoll`), mới nhất trước; mỗi mục có **số `#id` cố định** + **dòng trích nội dung** 💬; số = **toàn văn** thông báo đó, chữ = **lọc** theo tiêu đề/nội dung · notifications with a stable `#id` and a 💬 content preview; a number shows that notification's full text, a word filters | `102` · `#102` · `học phí` | stdout |
| `fap profile` | hồ sơ sinh viên (`GetStudentById`): tên/MSSV/email/ngày sinh/ngành/lớp… (chỉ hiện field có giá trị) · student profile | *(không · none)* | stdout |
| `fap applications` | đơn từ + **huy hiệu trạng thái** ⏳ đang xử lý / ✅ chấp nhận / ❌ từ chối + phản hồi (`GetApplication`), mới nhất trước · applications with status badges | *(không · none)* | stdout |
| `fap web [port]` | **dashboard web cục bộ** (Python stdlib, 0 dep) — bấm nút xem lịch/điểm/điểm danh; nút **sinh từ `COMMAND_INFO`** (thêm lệnh là có nút ngay) + ô **tham số** trên đầu trang (gõ `IAP491` / `weeks` / `8` rồi Enter để chạy lại lệnh đang xem); CHỈ localhost · local web dashboard (stdlib), buttons derived from `COMMAND_INFO` + an arg box, localhost-only | `[port]` mặc định `8000` · default `8000` | trình duyệt · browser; tiến trình nền |

### Đẩy · Push

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap calendar-auth` | xác thực Google Calendar 1 lần (mở trình duyệt) · authorize Google Calendar once (opens browser) | *(không · none)* — cần `credentials.json` ở gốc repo · needs `credentials.json` at repo root | `output/gcal_token.json` |
| `fap calendar-sync` | đẩy/cập nhật lịch lên Google Calendar (không tạo trùng) · push/update the timetable to Google Calendar (no duplicates) | *(không · none)* | sự kiện trên Calendar · events on calendar; tóm tắt stdout |
| `fap notify [<lệnh> [tham số]]` | gửi kết quả lên Telegram/Discord · push a view to Telegram/Discord | `test` (mặc định) hoặc **bất kỳ lệnh bot nào** — danh sách allowlist **sinh từ `COMMAND_INFO`** nên không bao giờ sót lệnh mới (`today`/`tomorrow`/`weekly`/`semester`/`attendance`/`banrisk`/`grades`/`grades-detail [môn]`/`status`/`whatif [điểm]`/`exams`/`gpa`/`notifications`/`all`…). Xem danh sách: `fap notify help`. Tham số **nhiều từ được giữ nguyên** · any bot command + its argument; multi-word args preserved | tin nhắn kênh · channel message; stdout |
| `fap watch-attendance [loop [phút]] [--absent-only]` | dò & báo khi **VỪA được điểm danh** (near real-time) · ping when attendance is just recorded | `loop [phút]` = chạy nền dò mỗi N phút (mặc định 15, tối thiểu 5); `--absent-only` = chỉ báo vắng/muộn · resident loop, one-shot, or absent-only | tin nhắn kênh + stdout; mốc lưu `output/attendance_state.json` |
| `fap watch-grades [loop [phút]]` | dò & báo khi có **ĐIỂM MỚI** (thành phần hoặc tổng kết) · ping on new component/final marks | `loop [phút]` = chạy nền (mặc định 30, tối thiểu 10) · resident loop or one-shot | tin nhắn kênh + stdout; mốc lưu `output/grade_state.json` |
| `fap notify notifications` | đẩy **thông báo trường MỚI** (dedupe theo `id`, lần đầu chỉ ghi mốc) · push only NEW school notifications Mỗi tin đẩy kèm **số `#id`** và **1 dòng trích nội dung** (≤140 ký tự) — gõ `/notifications <id>` để đọc toàn văn · each pushed item carries its `#id` and a one-line content preview (≤140 chars); send `/notifications <id>` for the full text. | *(không · none)* | tin nhắn kênh; mốc lưu `output/seen_notifications.json` |

### Bot tương tác · Interactive bots *(chạy nền · long-running)*

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap telegram-bot` | bot Telegram long-polling trả lời `/today` `/grades` `/whatif`… · interactive Telegram bot | *(không · none)* — cần `TELEGRAM_TOKEN` + `TELEGRAM_CHAT` | tiến trình nền · resident process (Ctrl+C để dừng) |
| `fap discord-bot` | bot Discord (prefix `!`) trả lời lệnh · interactive Discord bot | *(không · none)* — cần `pip install -e ".[bot]"` + `DISCORD_BOT_TOKEN` | tiến trình nền · resident process |

> Bot **chỉ trả lời chủ tài khoản** (Telegram: `TELEGRAM_CHAT`; Discord: `DISCORD_ALLOWED_USER_ID`). Mỗi lệnh gọi API FAP live. Chi tiết: [13-notify.md §8](13-notify.md). · Bots answer **only the account owner**; each command hits the live FAP API. See [13-notify.md §8](13-notify.md).

> 🎛️ **VI —** Cả hai bot có **bảng NÚT BẤM**: gõ `/menu` (Telegram) hoặc `!menu` / `/menu` (Discord) để chạy lệnh bằng một chạm, khỏi gõ. Nút sinh từ chính `COMMAND_INFO`. Chi tiết + giới hạn số nút: [13-notify.md §8.3](13-notify.md#83-nút-bấm--menu--buttons--menu).
> 🎛️ **EN —** Both bots ship a **BUTTON panel**: send `/menu` (Telegram) or `!menu` / `/menu` (Discord) to run a command with one tap. The buttons are generated from `COMMAND_INFO`. Details + button caps: [13-notify.md §8.3](13-notify.md#83-nút-bấm--menu--buttons--menu).

### Khác · Misc

| Lệnh · Command | Tác dụng · What it does | Tham số · Args | Kết quả/Output |
|---|---|---|---|
| `fap doctor` | tự kiểm tra môi trường (Python, token, `.env`, thư viện, kênh) · self-check (Python, token, `.env`, libs, channels) | *(không · none)* | stdout |
| `fap selftest` | chạy **2 bộ test offline** (50 unit + 77 integration, không cần token/mạng) — kiểm tool chạy đúng trên máy này · run the offline test suites | *(không · none)* | stdout + exit 0 nếu pass |
| `fap` *(không lệnh · no command)* | in bảng trợ giúp song ngữ · print the bilingual help | *(không · none)* | stdout |

---

## 2. Luồng đăng nhập · Login flow

**VI —** `fap login` thử *device flow* trước; nếu không khả dụng thì chuyển sang *Authorization Code + PKCE*: mở trình duyệt, đăng nhập Google @fpt.edu.vn. Sau khi đăng nhập, trình duyệt sẽ báo lỗi kiểu *"scheme ... not registered"* — **ĐÚNG, KHÔNG SAO**. Copy URL trên thanh địa chỉ rồi dán vào prompt, hoặc chạy `fap exchange "<url>"`. Bước cuối đổi `access_token` → token FAP qua endpoint `AuthenticationByFeId` (lấy trường `authenKey`).
**EN —** `fap login` tries the *device flow* first; if unavailable it falls back to *Authorization Code + PKCE*: it opens the browser for the Google @fpt.edu.vn login. After login the browser shows a *"scheme ... not registered"* error — **THIS IS NORMAL**. Copy the address-bar URL and paste it at the prompt, or run `fap exchange "<url>"`. The final step exchanges `access_token` → FAP token via the `AuthenticationByFeId` endpoint (reading the `authenKey` field).

**VI —** `fap refresh` làm mới token không cần trình duyệt bằng `refresh_token` — dùng được cho đến khi `refresh_token` hết hạn; lúc đó phải `fap login` lại.
**EN —** `fap refresh` renews the token headlessly with the `refresh_token` — it works until the `refresh_token` expires; then you must `fap login` again.

| Thông số OAuth · OAuth param | Giá trị · Value |
|---|---|
| issuer | `https://feid.fpt.edu.vn` |
| client_id | `fap-mobile-front-end` (public, PKCE, không secret · no secret) |
| redirect_uri | `io.identityserver.demo:/oauthredirect` |
| scope | `openid email profile offline_access` |

**Ví dụ · Examples**
```bash
fap login                                   # đăng nhập 1 lần · one-time login (hỏi CampusCode, vd FPTU)
fap exchange "io.identityserver.demo:/oauthredirect?code=...&state=..."
fap refresh                                 # làm mới headless · headless renew
fap whoami                                  # kiểm tra token đã lưu · check saved token
```

`output/token.json` (do `login`/`refresh`/`fap` tạo · created by `login`/`refresh`/`fap`) chứa các trường · holds: `authenkey`, `campus`, `rollnumber`, `email`, `fullname`.

> 🔎 **VI — Phát hiện token hết hạn (đã kiểm chứng live):** FAP trả `HTTP 200 + code 201` cho cả token sai (`message: "Token invalid"`) lẫn checksum lệch (`"...checksum không chính xác"`). Các lệnh dữ liệu giờ **báo rõ "Token hết hạn — chạy `fap refresh`"** thay vì trả rỗng im lặng. Lỗi checksum thường do **lệch giờ đầu giờ** nên tool **tự thử lại ±1h** một lần; nếu vẫn lỗi nghĩa là **đồng hồ máy bạn lệch giờ VN (UTC+7)** — chỉnh lại giờ hệ thống.
> 🔎 **EN — Expired-token detection (live-verified):** FAP returns `HTTP 200 + code 201` for both a bad token (`message: "Token invalid"`) and a drifted checksum (`"...checksum không chính xác"`). Data commands now **say "Token expired — run `fap refresh`"** instead of silently returning empty. Checksum errors are usually an **hour-boundary drift**, so the tool **auto-retries at ±1h** once; if it still fails, your **system clock is off from Vietnam time (UTC+7)** — fix the clock.

---

## 3. Endpoint & checksum theo từng lệnh dữ liệu · Per-command endpoint & checksum

**VI —** Đối chiếu công thức checksum tại `docs/05-checksum-map.md`. `cs12` = `getCheckSumAuthenicated`, `cs14` = `getCheckSumLogin`. Học kỳ (`Semester`) được chọn theo thứ tự: biến môi trường `FAP_SEMESTER` > tự dò qua `GetSemester` theo ngày > mặc định.
**EN —** Cross-check the checksum formulas in `docs/05-checksum-map.md`. `cs12` = `getCheckSumAuthenicated`, `cs14` = `getCheckSumLogin`. The semester (`Semester`) is chosen in this order: env `FAP_SEMESTER` > auto-detect via `GetSemester` by date > default.

### `fap grades`
**VI —** Gọi `GetStudentMark` với checksum `cs12(rollNumber, campusCode)` (mặc định). In bảng điểm + GPA tạm tính (chỉ tính môn đã có điểm).
**EN —** Calls `GetStudentMark` with checksum `cs12(rollNumber, campusCode)` (default). Prints the grade table + provisional GPA (graded subjects only).

```bash
fap grades
```

### `fap grades-detail [MÔN]`
**VI —** Trước hết gọi `GetStudentMark` để lấy `courseID` từng môn, rồi gọi `GetMarkByCourse` (tham số `CourseId`) cho điểm thành phần.
**EN —** First calls `GetStudentMark` to get each subject's `courseID`, then calls `GetMarkByCourse` (param `CourseId`) for the component grades.

> ✅ **VI — ĐÃ KIỂM CHỨNG (live):** `GetMarkByCourse` dùng checksum `cs12(rollNumber, campusCode)` (mặc định) → `code=200`; các biến thể khác (CourseId / login) → `code=201`. Đúng như `fap grades-detail` đang làm.
> ✅ **EN — VERIFIED (live):** `GetMarkByCourse` uses checksum `cs12(rollNumber, campusCode)` (default) → `code=200`; other variants (CourseId / login) → `code=201`. Matches what `fap grades-detail` already does.

**VI — Lọc 1 môn (khuyên dùng).** Không tham số, lệnh gọi `GetMarkByCourse` cho **MỌI** môn trong kỳ: kỳ 6 môn = **8 request**. Kèm mã/tên môn thì chỉ còn **3 request** — nhanh hơn hẳn và nhẹ cho server trường.
**EN — Filter to one subject (recommended).** With no argument the command calls `GetMarkByCourse` for **every** subject: a 6-subject term = **8 requests**. Naming a subject drops it to **3** — much faster and far gentler on the school's server.

**VI —** Cách khớp (`fapc/core/subjects.py` → `resolve()`), **không phân biệt hoa/thường**, ưu tiên giảm dần:
1. mã khớp **ĐÚNG** (`IAP301`) → 2. mã **BẮT ĐẦU BẰNG** (`iap`) → 3. mã **CHỨA** → 4. **TÊN môn CHỨA** (`lập trình`, chỉ có tác dụng khi đã chạy `fap subjects` để cache danh mục môn).
**EN —** Matching (`fapc/core/subjects.py` → `resolve()`) is **case-insensitive**, in this precedence: exact code → code prefix → code substring → **subject-name substring** (name matching only works after `fap subjects` has cached the catalog).

**VI —** Khớp **nhiều môn** → lệnh **liệt kê ứng viên** và bảo bạn gõ rõ hơn (không đoán bừa). **Không khớp môn nào** → liệt kê toàn bộ môn trong kỳ. Kỳ **chưa có điểm** vẫn báo "Chưa có dữ liệu điểm" như cũ (không bị đổi thành "không thấy môn").
**EN —** An **ambiguous** query **lists the candidates** and asks you to be more specific (it never guesses). **No match** → it lists every subject in the term. An **empty term** still says "No grades yet" (it is not turned into a "no such subject" message).

```bash
fap grades-detail                 # cả kỳ · the whole term (8 request cho kỳ 6 môn)
fap grades-detail IAP301          # đúng 1 môn · exactly one subject (3 request)
fap grades-detail iap             # khớp theo tiền tố mã · code-prefix match
fap grades-detail "lập trình"     # khớp theo TÊN môn (cần `fap subjects` trước) · name match
fap grades-detail --raw IAP301    # in NGUYÊN response GetMarkByCourse · raw diagnostic dump
```

> ⚠️ **VI —** `--raw` là **đường chẩn đoán**: nó KHÔNG gọi `GetCourseOfSemester`, nên chỉ tìm được môn trong danh sách của `GetStudentMark`. Môn mà `GetStudentMark` bỏ sót vẫn hiện ở bản thường nhưng **không tra được** ở `--raw`.
> ⚠️ **EN —** `--raw` is a **diagnostic path**: it does NOT call `GetCourseOfSemester`, so it can only resolve subjects that `GetStudentMark` returned. A subject `GetStudentMark` omits still shows in the normal view but is **not findable** under `--raw`.

### `fap attendance`
**VI —** Gọi `GetStudentAttendances` với checksum `cs12(rollNumber, campusCode)` (mặc định). In % chuyên cần + số buổi theo môn, kèm **giai đoạn môn** từ `startDate`/`endDate` và **các ngày vắng**. Dùng CHUNG renderer với bot `/attendance` nên CLI và chat luôn khớp.
- **Chưa bắt đầu** (`hôm nay < startDate`): hiện `⏳ chưa bắt đầu (từ dd/mm)` thay vì `0%` vô nghĩa, và **không** bị tính nguy cơ cấm thi.
- **Đang học**: `còn N ngày`; môn chưa có buổi nào được điểm danh hiện `chưa điểm danh buổi nào` (cũng không báo nguy cơ).
- **Đã kết thúc**: `✔ đã kết thúc`.
- **Ngày vắng** (`❌ Vắng 2: 12/06, 19/06`): lấy từ `attendanceStatus` của từng buổi trong `GetActivityStudent` — mã theo app chính thức: `P` có mặt, `A` vắng, còn lại = chưa diễn ra. Tốn **thêm 1 request** lịch học (`GetActivityStudent`; `api.call` chỉ cache khi `FAP_CACHE_MIN>0`, mặc định tắt); lấy lỗi thì chỉ thiếu ngày vắng, màn chính vẫn hiện. `banrisk` chỉ lấy lịch khi có môn dưới 80% — không có thì 0 request thêm.

**EN —** Calls `GetStudentAttendances` with checksum `cs12(rollNumber, campusCode)` (default). Prints attendance % and session counts per subject, plus the **term phase** from `startDate`/`endDate` and the **dates you were absent**. It shares the renderer with the bot's `/attendance`, so CLI and chat always match.
- **Not started** (`today < startDate`): shows `⏳ not started (from dd/mm)` instead of a meaningless `0%`, and is **not** counted as an exam-ban risk.
- **Ongoing**: `N days left`; a subject with no session recorded yet shows `no session recorded yet` (also no risk).
- **Ended**: `✔ ended`.
- **Absence dates** (`❌ Absent 2: 12/06, 19/06`) come from each session's `attendanceStatus` in `GetActivityStudent` — codes as the official app maps them: `P` present, `A` absent, anything else = not yet held. This costs **one extra** schedule request (`GetActivityStudent`; `api.call` only caches when `FAP_CACHE_MIN>0`, off by default); if it fails, only the absence dates are missing and the main view still renders. `banrisk` fetches the schedule only when some subject is below 80% — otherwise no extra request.

```bash
fap attendance
```

### `fap banrisk`
**VI —** Dùng cùng dữ liệu `GetStudentAttendances` (checksum `cs12(rollNumber, campusCode)`). Gắn cờ môn có **% chuyên cần hiện tại < 80%**. Đây chỉ là **PROXY (xấp xỉ)** cho quy định cấm thi thật của FPT (vốn tính trên tổng số buổi đã xếp lịch của kỳ), không phải con số chính thức. Trả **exit code 2** nếu có môn nguy cơ (tiện cho cron/CI), `0` nếu an toàn. Môn **chưa bắt đầu** hoặc **chưa có buổi nào được điểm danh** không bị tính nguy cơ (0% đầu kỳ là vô nghĩa) — cùng một luật với `/banrisk`, `/status`, `/weekly`, `/all`.
**EN —** Uses the same `GetStudentAttendances` data (checksum `cs12(rollNumber, campusCode)`). Flags subjects whose **current attendance % < 80%**. This is only a **PROXY (approximation)** of FPT's real exam-ban rule (which is based on the term's total scheduled sessions), not the official figure. Returns **exit code 2** when any subject is at risk (handy for cron/CI), `0` when safe. A subject that **hasn't started** or has **no session recorded yet** is not counted (0% at term start is meaningless) — the same rule as `/banrisk`, `/status`, `/weekly`, `/all`.

```bash
fap banrisk; echo "exit=$?"      # exit=2 nếu có nguy cơ · if at risk
```

### `fap ics` *(alias `fap run`)* và `fap notify`, `fap calendar-sync`
**VI —** Cả ba lấy lịch từ endpoint `GetActivityStudent` với checksum `cs12(rollNumber, campusCode)` (mỗi buổi gồm ngày + giờ + phòng + môn). `ics` ghi `output/lichhoc.ics`; `notify` gửi bản tóm tắt 1 ngày hoặc cả tuần lên Telegram/Discord; `calendar-sync` upsert sự kiện lên Google Calendar (chống trùng theo `iCalUID`). Múi giờ cố định `Asia/Ho_Chi_Minh` (không phải khóa `.env`).
**EN —** All three read the schedule from `GetActivityStudent` with checksum `cs12(rollNumber, campusCode)` (each session has date + time + room + subject). `ics` writes `output/lichhoc.ics`; `notify` sends a one-day or weekly digest to Telegram/Discord; `calendar-sync` upserts events to Google Calendar (deduped by `iCalUID`). Time zone is hard-coded `Asia/Ho_Chi_Minh` (not an `.env` key).

```bash
fap ics                          # -> output/lichhoc.ics
fap notify test                  # gửi tin thử · send a test message
fap notify today                 # lịch hôm nay · today's schedule
fap notify tomorrow              # lịch ngày mai · tomorrow's schedule
fap notify weekly                # TỔNG KẾT tuần: lịch + điểm danh + điểm · weekly recap (schedule+attendance+grades)
fap calendar-auth                # xác thực Google 1 lần · one-time Google auth
fap calendar-sync                # đẩy/cập nhật lịch · push/update the timetable
```

### `fap extract`
**VI —** Kéo hàng loạt endpoint chỉ-đọc về `output/api/<endpoint>.json`, rồi với mỗi môn trong `GetStudentAttendances` gọi thêm `getCourseAttendance`. Các endpoint dùng checksum không-mặc-định: `GetSemester` và `GetSubjets` dùng `cs14(campusCode)`; `GetSubjectBySemester` dùng `cs12(Semester, campusCode)`; `GetTop10News` dùng `cs12(type, campusCode)`; `GetSemesterMark` **không gửi checksum**. Các endpoint còn lại dùng mặc định `cs12(rollNumber, campusCode)`.
**EN —** Bulk-pulls read-only endpoints into `output/api/<endpoint>.json`, then for each subject from `GetStudentAttendances` it also calls `getCourseAttendance`. Non-default checksums: `GetSemester` and `GetSubjets` use `cs14(campusCode)`; `GetSubjectBySemester` uses `cs12(Semester, campusCode)`; `GetTop10News` uses `cs12(type, campusCode)`; `GetSemesterMark` **sends no checksum**. The rest use the default `cs12(rollNumber, campusCode)`.

```bash
fap extract                      # -> output/api/*.json
```

### `fap status`, `fap week`, `fap transcript`, `fap whatif`
**VI —** `status` (alias `dashboard`) gộp 3 nguồn trong một màn hình: `GetActivityStudent` (lịch hôm nay) + `GetStudentMark` (GPA tạm tính) + `GetStudentAttendances` (điểm danh + cảnh báo cấm thi) — đều `cs12(rollNumber, campusCode)`. `week` chỉ dùng `GetActivityStudent` (lọc theo tuần). `transcript` gọi `AcademicTranscript` (`cs12(rollNumber, campusCode)`); tài khoản chưa hoàn tất kỳ nào thì trả **rỗng**. `whatif` đọc `GetStudentMark` rồi tính **cục bộ** — trung bình cộng đơn giản, thang 0–10 (GPA thật của FPT tính theo tín chỉ; không gọi thêm API).
**EN —** `status` (alias `dashboard`) merges three sources on one screen: `GetActivityStudent` (today) + `GetStudentMark` (provisional GPA) + `GetStudentAttendances` (attendance + ban warning) — all `cs12(rollNumber, campusCode)`. `week` uses only `GetActivityStudent` (filtered to the week). `transcript` calls `AcademicTranscript` (`cs12(rollNumber, campusCode)`); **empty** for accounts with no completed semester. `whatif` reads `GetStudentMark` and computes **locally** — a simple unweighted mean, 0–10 scale (real FPT GPA is credit-weighted; no extra API call).

```bash
fap status                       # tổng quan · overview
fap all                          # MỌI mục 1 lần · everything at once
fap week                         # tuần này · this week
fap week next                    # tuần sau · next week
fap transcript                   # bảng điểm tích lũy · academic transcript
fap whatif                       # bảng dự kiến GPA · GPA projection
fap whatif 8                     # cần gì để đạt GPA 8 · what you need for GPA 8
```

> **VI —** `fap all` gọi nhiều endpoint liên tiếp. Trên **máy yếu / mạng chậm**, đặt `FAP_CACHE_MIN=2` để gộp các lượt gọi trùng trong 2 phút: `FAP_CACHE_MIN=2 fap all` (xem [15-config.md](15-config.md)).
> **EN —** `fap all` calls several endpoints back-to-back. On **weak machines / slow networks**, set `FAP_CACHE_MIN=2` to coalesce duplicate calls within 2 minutes: `FAP_CACHE_MIN=2 fap all` (see [15-config.md](15-config.md)).

> ⚠️ **VI —** Một số endpoint (`GeFeeByRoll`, `GetSemesterMark`, `GetVersion`) có thể trả **404** với tài khoản chưa hoàn tất kỳ nào — đây là do dữ liệu/server, không phải lỗi công cụ.
> ⚠️ **EN —** Some endpoints (`GeFeeByRoll`, `GetSemesterMark`, `GetVersion`) may return **404** for accounts with no completed semesters — that is server/data-driven, not a tool bug.

### `fap semester` — lịch CẢ KỲ · the whole-term schedule

**VI —** `GetActivityStudent` chỉ nhận tham số `Semester`, nghĩa là **một lời gọi đã trả về lịch CẢ KỲ** — `fap week` xưa nay lấy trọn rồi vứt đi ~90% để lọc 7 ngày. `fap semester` dùng đúng dữ liệu đó nên **không tốn thêm request** so với xem lịch tuần. Ba cách trình bày:
**EN —** `GetActivityStudent` only takes a `Semester` parameter, so **one call already returns the entire term** — `fap week` has always fetched it all and thrown ~90% away to filter 7 days. `fap semester` reuses exactly that data, so it costs **no extra request** over the weekly view. Three views:

| View | Gõ · Type | Nội dung · What you get |
|---|---|---|
| **pattern** *(mặc định · default)* | `fap semester` | vi · **mẫu lặp hằng tuần** mỗi môn (`🔁 SWP391: T2 07:30–09:50 📍AL-R201 ×10`) + danh sách **buổi lệch mẫu** (tối đa 8 buổi, dôi ra ghi `…+N buổi nữa`). Gọn nhất (~700 ký tự) — hợp để gửi chat. en · the repeating weekly slot per subject + off-pattern sessions (capped at 8). |
| **weeks** | `fap semester weeks` | vi · mỗi tuần **1 dòng**: `📌 Tuần 5 · 05/10–11/10 · 3 buổi: IAP301×1 PRN231×1 SWP391×1`. Số tuần là **số tuần THẬT của kỳ** (tra qua `GetSemester`; không tra được thì đánh số tuần liên tiếp). en · one line per week, numbered by the term's real week ordinal. |
| **list** | `fap semester list` | vi · liệt kê **từng ngày, từng buổi** cho cả kỳ — dài (kỳ ~60 buổi ≈ 3.7k ký tự), gửi chat sẽ bị **cắt thành nhiều tin**. en · day-by-day, session-by-session; long enough to be split into several chat messages. |

**VI —** Xem **kỳ khác**: thêm tên kỳ (`Fall2026`, `Spring2026`…). View và tên kỳ gõ **thứ tự nào cũng được**. Nếu kỳ đó trường **chưa xếp lịch** (hay gặp khi xem kỳ sau), lệnh báo rõ *"Kỳ này trường chưa xếp lịch"* + gợi ý các kỳ đang/sắp tới — không để màn hình trống.
**EN —** To view **another term**, add its name (`Fall2026`, `Spring2026`…). The view word and the term name may come in **either order**. If that term has **no published timetable** yet (common when peeking at the next term), the command says so and lists the current/upcoming terms instead of showing a blank screen.

> ℹ️ **VI — Muốn NHÌN dạng lịch (ô vuông theo ngày/giờ)?** Đừng chờ tính năng xuất ảnh — **đã có sẵn và tốt hơn**: [`fap ics`](#fap-ics-alias-fap-run-và-fap-notify-fap-calendar-sync) ghi `output/lichhoc.ics` để import một lần, còn [`fap calendar-sync`](12-google-calendar.md) đẩy thẳng lên Google Calendar và **đồng bộ lại được** (chống trùng theo `iCalUID`). Lịch nằm trong app Calendar của điện thoại thì cuộn được, tìm được, **tự nhắc**, hiện tiếng Việt + emoji chuẩn — thứ mà một tấm ảnh sinh sẵn không làm được.
> **EN — Want to *see* it as a calendar grid?** It already exists, and it beats a generated picture: `fap ics` writes `output/lichhoc.ics` for a one-off import, and `fap calendar-sync` pushes to Google Calendar and stays re-syncable (deduped by `iCalUID`). In your phone's calendar app it scrolls, searches, **reminds you**, and renders Vietnamese + emoji natively.
>
> **VI —** Cân nhắc rồi **bỏ**: render PNG bằng Pillow. Lý do đã kiểm chứng — Pillow **không kèm font nào**, font mặc định của nó vẽ `ế ữ ạ ễ Đ đ ơ ă` ra **đúng một ô vuông `.notdef`** (mask trùng byte với `漢`), và `📍 💻 ━` cũng là `.notdef` trong cả Segoe UI lẫn Arial ⇒ không tái dùng được chuỗi nào từ `fmt`. Thêm nữa `deploy/update.sh` cố định `EXTRAS=[gcal]` nên extra mới **sẽ không bao giờ được cài** trên server.
> **EN —** Considered and **dropped**: a Pillow PNG renderer. Verified: Pillow ships **zero fonts**, its default renders every Vietnamese diacritic as the identical `.notdef` box, `📍 💻 ━` are `.notdef` in Segoe UI and Arial too, and `deploy/update.sh` pins `EXTRAS=[gcal]` so a new extra would never install on the server.

```bash
fap semester                     # mẫu lặp hằng tuần + buổi lệch · weekly pattern + off-pattern
fap semester weeks               # mỗi tuần 1 dòng · one line per week
fap semester list                # liệt kê từng ngày · day-by-day list
fap semester Fall2026            # kỳ khác · another term
fap semester Fall2026 weeks      # kỳ khác + view (thứ tự tuỳ ý · either order)
fap notify semester              # đẩy lên Telegram/Discord · push to chat
```

**VI —** Ví dụ bản `pattern` (dữ liệu minh hoạ) · **EN —** Sample `pattern` output (illustrative data):

```
📚 Lịch cả kỳ Fall2026  ·  31 buổi
━━━━━━━━━━━━━━━━
🗓 07/09/2026 – 21/11/2026 · 11 tuần · 3 môn

🔁 IAP301: T6 09:10–11:30 📍AL-R305 ×10
🔁 PRN231: T4 12:30–14:50 📍BE-213 ×10
🔁 SWP391: T2 07:30–09:50 📍AL-R201 ×10

⚠️ Lệch mẫu (1 buổi):
   • 21/11 T7 07:30 SWP391 📍AL-R110

ℹ️ Mẫu suy từ lịch cả kỳ — KHÔNG phản ánh buổi huỷ / nghỉ lễ. Nghi ngờ tuần nào: fap week-exact
```

> ⚠️ **VI — KHÔNG phải nguồn chuẩn cho nghỉ lễ / buổi huỷ.** Mẫu lặp được **suy ra** từ `GetActivityStudent` (lịch xếp của cả kỳ), nên nó **không phản ánh** buổi bị huỷ, dời, hay tuần nghỉ lễ. Dòng ghi chú này được in **ngay trong kết quả**. Nghi ngờ một tuần cụ thể → dùng **`fap week-exact [week year]`** (`GetActivityStudentByWeek`) — đó mới là bản server trả cho đúng tuần đó.
> ⚠️ **EN — NOT authoritative for holidays / cancellations.** The pattern is **inferred** from `GetActivityStudent` (the term's *planned* timetable), so it does **not** reflect cancelled or moved sessions, nor holiday weeks. That caveat is printed **inside the output itself**. For a disputed week, use **`fap week-exact [week year]`** (`GetActivityStudentByWeek`) — that is the server's answer for that exact week.

> ⚠️ **VI —** `output/` chứa ĐIỂM / HỌC BẠ / TÀI CHÍNH / HỒ SƠ cá nhân — đã `.gitignore`, **KHÔNG** chia sẻ hay đẩy lên repo công khai.
> ⚠️ **EN —** `output/` holds grades / transcript / finance / personal profile — it is `.gitignore`d; do **NOT** share it or push it to a public repo.

---

## 4. Cấu hình `.env` liên quan · Relevant `.env` keys

**VI —** Đọc từ file `.env` ở gốc repo (mẫu: `.env.example`). Để trống = dùng mặc định / tắt.
**EN —** Read from `.env` at the repo root (template: `.env.example`). Empty = default / disabled.

| Khóa · Key | Ý nghĩa · Meaning | Lệnh ảnh hưởng · Affects |
|---|---|---|
| `FAP_LANG` | ngôn ngữ log/thông báo, `vi` (mặc định) hoặc `en` · log/message language, `vi` (default) or `en` | mọi lệnh in chữ · all printing commands |
| `FAP_SEMESTER` | ép học kỳ, vd `Spring2026` / `Summer2026` / `Fall2026`; để trống = tự dò qua `GetSemester` theo ngày · force the semester; empty = auto-detect via `GetSemester` by date | `grades`, `grades-detail`, `attendance`, `banrisk`, `ics`, `notify`, `calendar-sync`, `extract`, `status`, `today`, `tomorrow`, `week`, `semester`, `whatif` |
| `TELEGRAM_TOKEN` | token bot Telegram · Telegram bot token | `notify` |
| `TELEGRAM_CHAT` | chat id Telegram · Telegram chat id | `notify` |
| `DISCORD_WEBHOOK_URL` | webhook Discord · Discord webhook | `notify` |
| `GCAL_CALENDAR_ID` | lịch đích, mặc định `primary` · target calendar, default `primary` | `calendar-sync` |

> **VI —** Múi giờ `Asia/Ho_Chi_Minh` được gắn cứng trong mã, **không** phải khóa `.env`.
> **EN —** The `Asia/Ho_Chi_Minh` time zone is hard-coded, **not** an `.env` key.

> 🎓 **VI — Đổi kỳ cho MỘT lần chạy.** Chỉ **`fap semester <tên kỳ>`** nhận tên kỳ ngay trên dòng lệnh (vd `fap semester Fall2026 weeks`). Gõ **đúng cách viết của server** (`Fall2026`, `Spring2026`, `Summer2026`) — FAP **phân biệt hoa/thường** ở tham số `Semester`; gõ sai thì trả 0 buổi và lệnh sẽ **liệt kê các kỳ hợp lệ** cho bạn chép lại. Các lệnh còn lại (`week`, `grades`, `attendance`…) **không có cờ `--sem`**: muốn đổi kỳ thì đặt biến môi trường cho một lần chạy, vd `FAP_SEMESTER=Fall2026 fap week` (PowerShell: `$env:FAP_SEMESTER="Fall2026"; fap week`). `FAP_SEMESTER` luôn **ưu tiên cao nhất**.
> 🎓 **EN — Overriding the term for ONE run.** Only **`fap semester <term>`** takes a term name on the command line (e.g. `fap semester Fall2026 weeks`). Spell it **the way the server does** (`Fall2026`, `Spring2026`, `Summer2026`) — FAP's `Semester` parameter is **case-sensitive**; a wrong spelling returns 0 sessions and the command then **lists the valid term names** to copy from. Every other command (`week`, `grades`, `attendance`…) has **no `--sem` flag**: override via the env var for a single run, e.g. `FAP_SEMESTER=Fall2026 fap week` (PowerShell: `$env:FAP_SEMESTER="Fall2026"; fap week`). `FAP_SEMESTER` always **wins**.

---

## 5. Tệp & vị trí · Files & paths

**VI —** Tất cả nằm dưới thư mục gốc repo. `output/`, `.env`, `credentials.json` đều đã `.gitignore` (chứa bí mật/PII).
**EN —** All under the repo root. `output/`, `.env`, `credentials.json` are all `.gitignore`d (contain secrets/PII).

| Tệp · File | Nội dung · Contents | Lệnh tạo/đọc · Created/read by |
|---|---|---|
| `.env` / `.env.example` | cấu hình `KEY=VALUE` / mẫu · config `KEY=VALUE` / template | mọi lệnh đọc · read by all |
| `credentials.json` | OAuth desktop-client JSON của Google bạn tải về · Google OAuth desktop-client JSON you download | `calendar-auth` |
| `output/token.json` | token FAP: `authenkey`, `campus`, `rollnumber`, `email`, `fullname` · FAP token | `login` / `refresh` / `fap`; mọi lệnh dữ liệu đọc · all data cmds read |
| `output/oauth_tokens.json` | token FE Identity (kèm `refresh_token`) · FE Identity tokens | `login` / `refresh` |
| `output/.pkce_state.json` | verifier PKCE tạm thời · transient PKCE verifier | `login` -> `exchange` |
| `output/gcal_token.json` | token OAuth Google Calendar · Google Calendar OAuth token | `calendar-auth` / `calendar-sync` |
| `output/lichhoc.ics` | lịch đã xuất · exported calendar | `ics` |
| `output/api/*.json` | dump thô từng endpoint · raw per-endpoint dumps | `extract` |

> **VI —** Placeholder dùng trong tài liệu: `<campus>` (vd `FPTU`), `HE19xxxx`, `you@fpt.edu.vn` — thay bằng dữ liệu của bạn, đừng dán dữ liệu thật vào nơi công khai.
> **EN —** Placeholders used in docs: `<campus>` (e.g. `FPTU`), `HE19xxxx`, `you@fpt.edu.vn` — replace with your own data; never paste real data anywhere public.

---

## 6. Dạng không cài gói · Non-install fallback

**VI —** Nếu chưa `pip install -e .`, mọi lệnh đều có dạng tương đương:
**EN —** If you have not run `pip install -e .`, every command has an equivalent form:

```bash
python -m fapc login
python -m fapc extract
python -m fapc grades
# ...thay <command> bất kỳ ở trên · substitute any <command> above
```
