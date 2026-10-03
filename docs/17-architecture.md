# Kiến trúc & Logic toàn bộ code · Architecture & full logic

Tài liệu này mô tả **logic của từng phần** trong gói `fapc`: dữ liệu chảy thế nào, cơ chế API, và logic của mỗi lệnh. Dùng kèm [11-commands.md](11-commands.md) (tham chiếu lệnh) và [05-checksum-map.md](05-checksum-map.md) (công thức checksum).

---

## 1. Tổng quan kiến trúc · Layers

```
người dùng ─► fap <command> (fapc/app/cli.py)
                    │
   ┌────────────────┴───────────────────────────────────┐
   │  fapc/app/*  — TẦNG GIAO TIẾP (delivery)            │  phụ thuộc core
   │  cli · bot_core · dashboard · notify · webui        │
   │  attendwatch · gradewatch · telegrambot · discordbot · gcal
   └────────────────┬───────────────────────────────────┘
                    │ gọi
   ┌────────────────┴───────────────────────────────────┐
   │  fapc/core/*  — TẦNG DỮ LIỆU (data)                 │  KHÔNG import app
   │  api (HTTP+checksum+auth) · apiv2 (v2 opt-in)       │
   │  auth (OAuth) · schedule · grades · attendance ·    │
   │  transcript · whatif · extras · extract · conduct   │
   └────────────────┬───────────────────────────────────┘
                    │
   fapc/  (shared): config (.env) · i18n (song ngữ) · fmt (định dạng)
                    │
            https://api.fpt.edu.vn/fap/api/MyFAP/<endpoint>        ← v1 (mặc định)
            https://fap-proxy.fpt.edu.vn/MyFAP/<endpoint>          ← v2 (FAP_API_VERSION=v2, thử nghiệm)
```

`analysis/` (ngoài package, không được `fapc` import): `keys_schema.py` (sơ đồ khoá của dump, chỉ tên khoá) và `apk_drift.py` (so APK/bundle myFAP với hằng số + endpoint fap-cli, **offline**, thư viện chuẩn; exit `0/1/2` cho cron/CI; `--write-v2-key` ghi `FAP_V2_KEY` vào `.env` mà không in giá trị) — xem [20-api-fields](20-api-fields.md) §5.1.

**Quy tắc bất biến:** `core/` không bao giờ import `app/` (kiểm bằng test). Mọi lệnh CLI/bot/web cuối cùng đều gọi cùng các hàm `fetch_*` trong `core/`, nên hành vi nhất quán.

**Đường dữ liệu 1 lệnh** (vd `fap grades`):
`cli.main` → `grades.report()` → `grades.fetch_marks()` → `api.call("GetStudentMark", …)` → HTTP → `check_auth()` → `as_list()` → in qua `fmt`.

---

## 2. Lõi API · `core/api.py`

| Hàm | Logic |
|---|---|
| `creds()` | Đọc `output/token.json` (do login/refresh tạo) → `(token, campus, roll)`. Thiếu token → `SystemExit("… fap login")`. Fallback RKStorage chỉ cho hướng máy ảo legacy. |
| `checksum_auth(a,b)` | `base64(HMAC_SHA1(SECRET, a + "MYFAP" + b + "DD/MM/YYYY HH:00"))` rồi `=`→`%3d`, space→`+`. **HH = giờ Việt Nam (UTC+7)** — checksum đổi theo từng giờ. |
| `checksum_login(campus)` | Như trên nhưng message = `LOGIN_PREFIX + campus + giờ`. Dùng cho GetSemester/GetSubjets/login. |
| `call(endpoint, params, roll, campus, checksum_value=None)` | Dựng URL, gắn checksum, GET. **`checksum_value`**: `None`=mặc định `cs12(roll,campus)`; `False`=không gửi; chuỗi=override. Trả `(http_status\|None, json\|text)`. **Đầu hàm:** so dấu `api_version` trong `token.json` với `FAP_API_VERSION` (lệch → `SystemExit` "chạy `fap refresh`"); `FAP_API_VERSION=v2` → rẽ sang `apiv2.call_v2` (cùng hợp đồng trả về). `GetAllActiveCampus` (`fap campuses`) luôn đi v1, không cần token. |
| `check_auth(http, data)` | Phát hiện token hết hạn (đã probe live): HTTP 401/403, HTTP 200 + `code="201"` với message chứa "token", **hoặc thân lỗi phiên kiểu v2** (`code` = `401` chuỗi/số, hoặc `errorMessage` = `Unauthorized`) → raise `SystemExit("… fap refresh")`; message chứa "checksum" → báo lệch giờ. **HTTP 500 không tính** là hết phiên (tránh vòng refresh). Nhờ vậy `fetch_*` không trả `[]` im lặng. Bản THUẦN không raise: `is_session_expired(http, data)` cho watcher/`courses`/`grades`. |
| `classify_drift(http, body, content_type)` | THUẦN, **0 request thêm**: phản hồi v1 trông như route đã dời/tắt? 301/302/303/307/308 → `redirect`, 410 → `gone`, 404 **thân không phải JSON** → `not_found`; 404 có JSON và 404 của endpoint vốn đã 404 (`GetSemesterMark`, `GetVersion`, `GetCourseOfSemester`) không tính. Tín hiệu đầu tiên mỗi tiến trình in **1** gợi ý song ngữ ra `stderr` (chỉ tên endpoint + mã HTTP, không URL/token). |
| `default_semester(when)` | Đoán kỳ theo **ngày VN**: Spring (T1–4) / Summer (T5–8) / Fall (T9–12) + năm. Fallback đúng cho **mọi sinh viên, mọi kỳ** (không hardcode). |
| `select_semester(semesters, now)` | THUẦN — **một** quy tắc chọn kỳ cho cả `current_semester` lẫn `schedule.pick_semester`: kỳ **đầu tiên** (theo thứ tự server) chứa hôm nay, so theo **ngày** — **ngày cuối kỳ vẫn trong kỳ** (cố ý lệch app myFAP 2.0.5 vốn so thời điểm với `endDate` 00:00); không có → kỳ có `startDate` **gần nhất** (hai phía, hoà giữ kỳ đứng trước, như app); mục lỗi/thiếu tên bị bỏ qua. Trả `None` nếu không kỳ nào dùng được. |
| `current_semester()` | `FAP_SEMESTER` (env) > tự dò qua `GetSemester` + `select_semester` (**parse an toàn từng mục** để 1 ngày-lỗi không kéo sập) > `default_semester()`. **LUÔN trả 1 chuỗi, không raise** (kể cả `SystemExit` của v2 thiếu khoá / token lệch phiên bản). |

**3 cơ chế chống lỗi trong `call()`:**
1. **Cache trong-bộ-nhớ** (opt-in `FAP_CACHE_MIN` phút): key = endpoint+params (KHÔNG gồm checksum vì đổi theo giờ); chỉ cache HTTP 200 + code≠201; tự hết hạn.
2. **Retry checksum ±1h**: nếu lỗi checksum (lệch giờ ngay đầu giờ), tự thử lại với giờ `{now, now+1, now−1}` (chỉ khi dùng checksum mặc định).
3. **`allow_redirects=False`**: token nằm trong query string → KHÔNG đi theo 30x sang host khác (chống rò token). Lỗi mạng trả chuỗi **không chứa URL/token**.

### 2.1 API v2 opt-in · `core/apiv2.py`

**OPT-IN, THỬ NGHIỆM, CHƯA kiểm chứng với server thật** — chỉ chạy khi `FAP_API_VERSION=v2`; mặc định v1 và `call()` không bao giờ rẽ vào đây. Đặc tả + cách bật: [21-api-v2](21-api-v2.md) §5.

| Hàm | Logic |
|---|---|
| `normalize_version()` / `api_version()` | `FAP_API_VERSION` → `v1`/`v2` (không phân biệt hoa/thường); giá trị lạ → `v1` + **1** cảnh báo song ngữ (không in lại giá trị). Đọc **lúc gọi** qua `config.api_version_raw()`. |
| `v2_key()` | Đọc `FAP_V2_KEY` qua `config.v2_key_raw()` ngay lúc ký; thiếu → `SystemExit` hướng dẫn trích khoá (**0 request**). Khoá không bao giờ vào biến module, URL, log, lỗi hay `token.json`. |
| `checksum_v2()` / `build_headers_v2()` | THUẦN: chữ ký HMAC-SHA256 theo **epoch giây** + header kiểu app (Bearer + `Checksum: <sig>:<epoch>`) — không cần thử ±1h. Luôn ký bằng **token của chính người dùng**. |
| `v2_request()` / `call_v2()` | Bảng `ENDPOINTS` (tên v1 → đường dẫn + tham số v2) → GET `fap-proxy`, timeout 15 s, không theo redirect; cùng hợp đồng `(http, body)`, cùng cache `FAP_CACHE_MIN` (khoá tách riêng). Endpoint GHI + `GetApiActive` nằm trong `DENY` → từ chối **trước khi** chạm mạng; `GetStudentRate` không có trên v2 (`fap extract` bỏ qua). |
| `session_version()` / `check_session_version()` | Đọc dấu `api_version` trong `token.json` (thiếu = `v1`); lệch `FAP_API_VERSION` → `SystemExit` "chạy `fap refresh`". |
| `scrub()` | Che khoá v2 (+ token) nếu lỡ lọt vào một chuỗi log. |

---

## 3. Đăng nhập · `core/auth.py`

OAuth **FE Identity (IdentityServer)**, client công khai `fap-mobile-front-end` (PKCE, không secret):
- `cmd_login()`: thử **device flow** trước; không được thì **Authorization Code + PKCE** (mở browser; URL redirect `io.identityserver.demo:/oauthredirect?code=…` báo "scheme not registered" là đúng → copy/paste).
- `exchange_code(url)`: đổi `code` → `access_token` (+ `refresh_token`).
- bước cuối `AuthenticationByFeId` (checksum login) đổi `access_token` → **token FAP** (`authenKey`) → lưu `output/token.json` (chmod 0600 trên POSIX). `_do_fap` chốt phiên bản API **một lần** rồi **đóng dấu** `"api_version"` vào `token.json` (v1 lẫn v2); với `FAP_API_VERSION=v2` bước này là POST `fap-proxy …/AuthenticationByFeId` body `{token}` ký bằng chính access token FE (thiếu `FAP_V2_KEY` → log hướng dẫn, trả `None`, 0 request).
- `refresh_tokens()`: làm mới headless qua `refresh_token` (đến khi nó hết hạn thì login lại).
- `_redact()`: che token/PII khi dump debug (kể cả `authorization`, `checksum`, `v2_key` của v2); lỗi mạng không in URL.

---

## 4. Logic các module dữ liệu · `core/`

**schedule.py** — `parse_session()` đọc `date` + `slotTime` "(HH:MM - HH:MM)": thử 3 format ngày (`m/d/Y` ưu tiên vì FAP dùng US), đánh dấu *ambiguous* nếu cả ngày & tháng ≤12, +1 ngày nếu kết thúc qua nửa đêm. `sessions_on_day()` lọc+sort theo giờ (dùng chung cho dashboard/notify). `build_ics()` xuất `.ics` (VTIMEZONE Asia/Ho_Chi_Minh, skip buổi không parse được). `fetch_week_by_date()`/`fetch_week_activities()` cho `week-exact` (lấy TKB tuần thẳng từ server).

**subjects.py** — danh mục môn (GetSubjets, checksum_login). `index_of()` THUẦN → `{mã: {en, vi, credits, replacedBy}}`. `load()` đọc cache `output/subjects_catalog.json` (memo trong tiến trình, KHÔNG tự fetch ở lệnh nóng); `refresh()` fetch+lưu (lệnh `fap subjects`). `label()`/`name()`/`credit_of()` tự nạp cache, **degrade êm về mã trơ / 0 tín chỉ** khi chưa cache → mọi nơi gọi đều an toàn. Đây là lớp join để API mã-trơ hiện **tên môn** + cấp **tín chỉ** cho GPA theo trọng số.

**grades.py** — `fetch_marks()` (GetStudentMark). `_gpa()` = TB cộng môn đã có điểm; `term_gpa()` → `(gpa, weighted)`: có tín chỉ (subjects đã cache) thì tính **theo trọng số tín chỉ**, không thì rơi về TB cộng. `_components()`/`_normalize_components()` (GetMarkByCourse): nhận cả list lẫn dict. `fetch_components()` trả `None` khi lấy hỏng. `detail_text()` render điểm thành phần + **tên môn** ở tiêu đề + dòng dự đoán "cần X/10 để qua" (qua `whatif.predict_course`, import trễ tránh vòng). **HỢP NHẤT** `GetStudentMark` với `courses.course_id_map()` (GetCourseOfSemester) → môn bị `GetStudentMark` bỏ sót / thiếu `courseID` vẫn lấy được điểm thành phần; endpoint lỗi/404 → cmap rỗng → giữ nguyên hành vi cũ.

**courses.py** — lớp đăng ký trong kỳ (GetCourseOfSemester). `fetch_courses()` trả `None` khi 404/lỗi (phân biệt rỗng-thật). `course_id_map()` THUẦN → `{mã: courseId}` (vá điểm thành phần). `roster()`/`roster_from_activity()` THUẦN → 1 dòng/môn (môn/lớp/GV/phòng); `courses_text()` ưu tiên GetCourseOfSemester, **fallback gộp từ GetActivityStudent** nếu endpoint không dùng được. Mọi field dò đa-biến-thể (`courseId`/`courseID`/`CourseId`…).

**attendance.py** — `_pct()` trả `None` nếu CHƯA có dữ liệu (khác 0% thật). `_at_risk()` = `pct < 80%`. `banrisk()` trả exit code 2 nếu có nguy cơ (tiện cron). `report()` hiện thêm **tên môn** (subjects).

**transcript.py** — `_weighted_gpa()` = Σ(điểm×tín chỉ)/Σ(tín chỉ) — **GPA chính thức theo tín chỉ** (nguồn AcademicTranscript). `gpa_text()` gộp toàn khoá + từng kỳ.

**whatif.py** — `_split()` tách môn đã/chưa có điểm. `needed_average(target,…)` cho mô phỏng GPA cả kỳ. `predict_course(components,target)` THUẦN: từ trọng số+giá trị các đầu điểm 1 môn → "cần TB bao nhiêu ở phần còn lại để **qua môn**" (trọng số tự triệt tiêu nên không cần biết %/phân số); `predict_line()` render 1 dòng. `run()` in bảng dự kiến (5–10) hoặc điểm-cần.

**extras.py** — `campuses()` (GetAllActiveCampus, KHÔNG cần token — chọn campus trước login), `exams_text()`/`exams_ics()` (lịch thi → `.ics` + nhắc trước 1 ngày, parse ngày/giờ generic; `exam_countdown()` dùng **chung** danh sách khoá `_EX_SUBJ`/`_EX_ROOM`/`_EX_TYPE`, không phân biệt hoa/thường, gồm cả khoá thẻ thi của app 2.0.5), `notifications_text()` (GetNotificationByRoll, mới nhất trước), `news()` (`_news_get` so khoá không phân biệt hoa/thường: `tittle`/`content`/`createDate` lẫn `Title`/`Contents`/`EntryDate`/`EntryBy`), `fees()` (`fee_details_text()` THUẦN xét HTTP trước: 404 `GeFeeByRoll` = "không dùng được với tài khoản này"; `invoice_text()` in link hoá đơn điện tử `dng.fpt.edu.vn` — **chỉ CLI**, vì link chứa MSSV). `profile_text(full=False)`: bot/web **ẩn** ngày sinh/SĐT/CCCD; chỉ `fap profile` (CLI) truyền `full=True`.
- **Việc cần làm (to-do):** `todo_fetch()` gọi 3 GET (`CheckOpenFeedBack`, `CheckUpdateProfile`, `GetApplication`), **mỗi nguồn cô lập lỗi** → `None` = "không biết"; `todo_items()`/`todo_block()` THUẦN (không bao giờ nói "không có việc" khi chưa kiểm được). `_profile_flag_v2()` quy `CheckUpdateProfile` kiểu v2 (khác rỗng = phải cập nhật) về boolean kiểu v1. Chỉ **nhắc** dùng kênh chính thức — không gọi `AddRate`/`SubmitStudentFeedback`; `GetStudentRate` không dùng.
- **Đơn đổi trạng thái:** `fetch_applications_checked()` (list khi lấy được, `None` khi không biết) + `app_changes(prev, rows)` THUẦN (khoá theo `w_APP_ID` không phân biệt hoa/thường; lần đầu ghi mốc im lặng; đơn biến mất bỏ khỏi mốc; danh sách rỗng khi mốc có đơn = giữ mốc; `3`/`1` xếp đầu) + `app_changes_text()`.

**conduct.py** — `GetDiemphongtrao`. `is_no_data()` THUẦN: chỉ `code 201` + `errorMessage` NullReference (và `message` **không** nhắc token/checksum) mới là "chưa có điểm"; mọi `201` khác đi qua `check_auth` (token hết hạn / lệch giờ được **báo**, không bị giấu).

**extract.py** — `fap extract` dump A) RKStorage (nếu có) B) ~21 endpoint read-only C) `getCourseAttendance` từng môn D) `GetMarkByCourse` từng môn E) `GetWeekByDate`→`GetActivityStudentByWeek`. Giãn cách `FAP_EXTRACT_DELAY` giây giữa lượt. Trên v2 bỏ qua `GetStudentRate` (không có trên v2) và ghi chú "API v2 (thử nghiệm)" ở dòng đầu.

---

## 5. Logic tầng giao tiếp · `app/`

**bot_core.py** — `handle(cmd, arg)` là **lõi chung của bot + web + notify**: chuẩn hoá lệnh (gồm `_`→`-`, để tên menu `grades_detail` khớp `grades-detail`), `creds()`+`current_semester()` một lần, route tới `_*_text()`. Bọc `try/except SystemExit` → token hết hạn trả **lời nhắn** thay vì sập bot/web. `all_text()` lấy marks/att **đúng 1 lần** rồi chia sẻ (không gọi trùng endpoint), cuối tin là khối **việc cần làm** (`todo_text`, tự cô lập lỗi từng nguồn nên không làm sập cả tin); `/todo` là lệnh riêng trong `COMMAND_INFO` (24 lệnh). `COMMAND_INFO` là **nguồn lệnh duy nhất** → suy ra `COMMANDS` + `menu_commands()` (cấp cho menu gợi ý Telegram & slash Discord) + `command_groups()` (cấp cho `help_text()` **và** nút bấm `webui`, thay 2 danh sách chép tay từng lệch mất 6 lệnh; lệnh chưa xếp nhóm tự rơi vào nhóm cuối "Lệnh khác" nên **không thể sót**) + allowlist của `notify` + **nhánh dự phòng của CLI** (`cli._core_cmd()` → lệnh nào chưa có nhánh CLI riêng vẫn chạy qua `handle()`; trước đây `fap today`/`fap tomorrow` in nhầm HELP). `semester_arg(arg, sem)` là hàm THUẦN tách `"FALL2025 weeks"` → `(view, kỳ)` cho `/semester`.

**notify.py** — `push()` gửi Telegram + Discord (kiểm HTTP status — `requests.post` không raise với 4xx; xử lý 429 Retry-After). `fap notify notifications` chạy **hai việc cô lập lỗi trong cùng một lượt** (lỗi vẫn ném lại sau cùng → exit ≠ 0 cho cron/systemd): `push_new_notifications()` chỉ đẩy thông báo MỚI (dedupe theo `id`, sentinel `None`=chưa baseline; bỏ qua khi fetch rỗng; file hỏng → cô lập `.corrupt` + rebaseline) và `push_application_changes()` báo **đơn đổi trạng thái** (mốc `output/applications_state.json`, ghi atomic tmp-theo-PID + `0600`, file hỏng → `.corrupt` + ghi mốc lại; lấy đơn thất bại → bỏ lượt, giữ mốc). `fap notify today` gắn khối **việc cần làm** (`_todo_tail()`) **chỉ khi có ≥1 việc**; lỗi gì ở đó cũng không làm mất digest lịch học.

**dashboard.py** — `status()` (hôm nay + GPA tạm tính + điểm danh + cảnh báo cấm thi), `week()` (lọc từ kỳ; header kèm `· Tuần N/M` khi tra được mốc kỳ, im lặng bỏ qua nếu không), `week_exact()` (GetActivityStudentByWeek — chuẩn cho tuần nghỉ lễ; render generic, group theo ngày), `semester_text()`/`semester_view_text()` (**lịch CẢ KỲ**, 3 view `pattern|weeks|list`). `GetActivityStudent` vốn trả **trọn kỳ** nên view cả kỳ **không tốn request thêm**; `_resolve_sem()` dùng CHUNG 1 lời gọi `GetSemester` cho cả việc chọn kỳ lẫn tra mốc ngày (giữ `fap week` ở đúng 2 request). `semester_view_text()` là **hàm THUẦN** (nhận list buổi → chuỗi, test offline được) và **luôn in ghi chú**: mẫu suy từ lịch xếp, KHÔNG phản ánh buổi huỷ/nghỉ lễ → tuần nghi ngờ dùng `fap week-exact`.

**attendwatch.py / gradewatch.py** — kiến trúc giống nhau: `compute()` là **lõi THUẦN** (không mạng/IO, test offline được) so trạng thái với lần trước → sự kiện mới; `poll()` gọi mạng + lưu `output/*_state.json` (ghi atomic, file hỏng → `.corrupt`); `loop()` chạy nền (khung giờ 06–22, **tự refresh token ~50'** để service sống lâu). Chống spam: mỗi buổi/điểm chỉ báo 1 lần; so điểm theo **số** (`8.5`≡`8.50`); fetch hỏng → giữ mốc cũ (không nuốt sự kiện).

**webui.py** — `http.server` stdlib, **CHỈ bind 127.0.0.1**. Trang 1 file: nút nhóm theo chủ đề **sinh từ `command_groups()`** → `GET /q?c=<lệnh>[&a=<tham số>]` → `handle()`; ô **tham số** trên header (Enter = chạy lại lệnh hiện tại) cho `grades-detail IAP491` / `semester weeks` / `whatif 8`, kẹp `ARG_MAX=64` ký tự + gom khoảng trắng; `/me` lấy tên/MSSV từ token.json cho header. Tự bật `FAP_CACHE_MIN=2` (bấm nhiều không gọi lại API). Responsive + sáng/tối tự động + tự-làm-mới 60s.

**telegrambot.py / discordbot.py** — long-poll/gateway, gọi `handle()` trong thread executor (không chặn loop). **Chỉ trả lời chủ tài khoản** (Telegram `TELEGRAM_CHAT` bắt buộc; Discord `DISCORD_ALLOWED_USER_ID` bắt buộc, mở cho mọi người phải cố ý `DISCORD_ALLOW_ANYONE=1`). Lúc khởi động **tự đăng ký menu lệnh gợi ý**: Telegram `setMyCommands` (nút Menu ☰ + gợi ý khi gõ `/`); Discord `app_commands` slash (`tree.sync()` toàn cục, bọc try/except → thiếu thì vẫn chạy prefix `!`). Cả hai không sống-còn: lỗi đăng ký menu thì bot vẫn chạy. **Bảng nút bấm** (`/menu`, `!menu`) cũng **sinh từ `menu_commands()`**: Telegram `inline_keyboard` 12 nút/3 cột, gắn vào **mẩu CUỐI** khi tin bị `fmt.chunks()` cắt, `callback_query` luôn `answerCallbackQuery` **trước** rồi mới chạy lệnh; Discord `discord.ui.View` tối đa 25 nút (5×5) + `add_view()` lúc `on_ready` để nút sống qua restart, câu trả lời ngắn bọc **embed** (quá khổ → tự lùi về plain-text chia mẩu, không cắt cụt). Nút dùng **cùng hàm kiểm quyền** với lệnh gõ tay (`_dispatch()` / `_owner()`) nên không thể lệch.

**reminders.py** — **nhắc trước mỗi tiết** cho bot tương tác. Lõi THUẦN `due_reminders(sessions, now, lead, sent)` (tiết bắt đầu trong `[now, now+lead]` & chưa nhắc) + `reminder_text()` → test offline. `ClassReminder.tick()` lo phần mạng: nạp TKB hôm nay (cache ~3h, reset `sent` khi sang ngày), **tự refresh token ~50'** (vá việc bot tương tác trước đây không refresh → chết token sau ~1h). Telegram tick mỗi vòng long-poll; Discord chạy task nền 60s và **DM** chủ tài khoản. `FAP_REMIND_MINUTES=0` → tắt.

**gcal.py** — đẩy `.ics` lên Google Calendar (OAuth riêng, upsert chống trùng theo `iCalUID`).

---

## 6. Shared

- **config.py** — nạp `.env` (strip quote, không hỗ trợ comment cuối dòng), phơi `TELEGRAM_*`, `DISCORD_*`, `GCAL_*`, `FAP_*`. `api_version_raw()` / `v2_key_raw()` là **hàm** (đọc lúc gọi, không chụp lúc import) — `FAP_V2_KEY` cố ý **không** nằm trong biến module nào.
- **i18n.py** — `t(vi, en)` chọn theo `FAP_LANG`.
- **fmt.py** — định dạng THUẦN dùng chung: `weekday`, `room` (💻/📍), `header` (tiêu đề + đường kẻ), `fmt_date`, `status_label`, `safe_float`, `has_mark`, `gpa_val`, `table` (bảng generic theo đúng field server).

---

## 7. Hiệu năng & máy yếu → mạnh · Performance knobs

| Cần | Cách | Lệnh ảnh hưởng |
|---|---|---|
| Bớt gọi API trùng | `FAP_CACHE_MIN=2..5` (cache phản hồi N phút) | `web`, `status`, `all` |
| Giãn cách extract | `FAP_EXTRACT_DELAY=0.7..2` giây/lượt | `extract` |
| Watcher nhẹ | `watch-attendance loop 30` / `watch-grades loop 60` (phút lớn hơn) | watchers |
| Đỡ spam | `--absent-only` (chỉ báo vắng), watch-grades chỉ báo điểm mới | watchers |
| Máy yếu chạy web | `web` đã tự bật cache 2' | `web` |

Hồ sơ máy yếu→mạnh chi tiết (cron/systemd/Docker/at-logon): xem [14-deploy.md](14-deploy.md) và `deploy/README.md`.

---

## 8. Kiểm thử & bảo mật

- **Test**: `python tests/test_logic.py` (~180 unit, logic thuần) + `python tests/integration_offline.py` (~195 integration, mock mạng — gồm vòng tròn v2 với mạng giả) — hoặc gói gọn: **`fap selftest`**. Cả hai KHÔNG cần token/mạng; test nào thử gọi mạng thật là FAIL.
- **Bảo mật**: token nằm trong query `Authen` (lỗi mạng không in URL); `output/`, `.env`, `credentials.json`, `device-data/` đều `.gitignore`; `FAP_V2_KEY` chỉ ở `.env`/biến môi trường, không bao giờ in (kể cả `fap doctor`, chỉ báo có/thiếu); web chỉ localhost; bot khoá theo chủ tài khoản; chỉ thao tác tài khoản của chính bạn (xem [SECURITY.md](../SECURITY.md)).
