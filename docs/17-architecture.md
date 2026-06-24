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
   │  api (HTTP+checksum+auth) · auth (OAuth)            │
   │  schedule · grades · attendance · transcript ·      │
   │  whatif · extras · extract                          │
   └────────────────┬───────────────────────────────────┘
                    │
   fapc/  (shared): config (.env) · i18n (song ngữ) · fmt (định dạng)
                    │
            https://api.fpt.edu.vn/fap/api/MyFAP/<endpoint>
```

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
| `call(endpoint, params, roll, campus, checksum_value=None)` | Dựng URL, gắn checksum, GET. **`checksum_value`**: `None`=mặc định `cs12(roll,campus)`; `False`=không gửi; chuỗi=override. Trả `(http_status\|None, json\|text)`. |
| `check_auth(http, data)` | Phát hiện token hết hạn (đã probe live): HTTP 401/403 **hoặc** HTTP 200 + `code="201"` với message chứa "token" → raise `SystemExit("… fap refresh")`; message chứa "checksum" → báo lệch giờ. Nhờ vậy `fetch_*` không trả `[]` im lặng. |
| `default_semester(when)` | Đoán kỳ theo **ngày VN**: Spring (T1–4) / Summer (T5–8) / Fall (T9–12) + năm. Fallback đúng cho **mọi sinh viên, mọi kỳ** (không hardcode). |
| `current_semester()` | `FAP_SEMESTER` (env) > tự dò qua `GetSemester` (so ngày trong khoảng start/end, **parse an toàn từng mục** để 1 ngày-lỗi không kéo sập) > `default_semester()`. **LUÔN trả 1 chuỗi, không raise.** |

**3 cơ chế chống lỗi trong `call()`:**
1. **Cache trong-bộ-nhớ** (opt-in `FAP_CACHE_MIN` phút): key = endpoint+params (KHÔNG gồm checksum vì đổi theo giờ); chỉ cache HTTP 200 + code≠201; tự hết hạn.
2. **Retry checksum ±1h**: nếu lỗi checksum (lệch giờ ngay đầu giờ), tự thử lại với giờ `{now, now+1, now−1}` (chỉ khi dùng checksum mặc định).
3. **`allow_redirects=False`**: token nằm trong query string → KHÔNG đi theo 30x sang host khác (chống rò token). Lỗi mạng trả chuỗi **không chứa URL/token**.

---

## 3. Đăng nhập · `core/auth.py`

OAuth **FE Identity (IdentityServer)**, client công khai `fap-mobile-front-end` (PKCE, không secret):
- `cmd_login()`: thử **device flow** trước; không được thì **Authorization Code + PKCE** (mở browser; URL redirect `io.identityserver.demo:/oauthredirect?code=…` báo "scheme not registered" là đúng → copy/paste).
- `exchange_code(url)`: đổi `code` → `access_token` (+ `refresh_token`).
- bước cuối `AuthenticationByFeId` (checksum login) đổi `access_token` → **token FAP** (`authenKey`) → lưu `output/token.json` (chmod 0600 trên POSIX).
- `refresh_tokens()`: làm mới headless qua `refresh_token` (đến khi nó hết hạn thì login lại).
- `_redact()`: che token/PII khi dump debug; lỗi mạng không in URL.

---

## 4. Logic các module dữ liệu · `core/`

**schedule.py** — `parse_session()` đọc `date` + `slotTime` "(HH:MM - HH:MM)": thử 3 format ngày (`m/d/Y` ưu tiên vì FAP dùng US), đánh dấu *ambiguous* nếu cả ngày & tháng ≤12, +1 ngày nếu kết thúc qua nửa đêm. `sessions_on_day()` lọc+sort theo giờ (dùng chung cho dashboard/notify). `build_ics()` xuất `.ics` (VTIMEZONE Asia/Ho_Chi_Minh, skip buổi không parse được). `fetch_week_by_date()`/`fetch_week_activities()` cho `week-exact` (lấy TKB tuần thẳng từ server).

**subjects.py** — danh mục môn (GetSubjets, checksum_login). `index_of()` THUẦN → `{mã: {en, vi, credits, replacedBy}}`. `load()` đọc cache `output/subjects_catalog.json` (memo trong tiến trình, KHÔNG tự fetch ở lệnh nóng); `refresh()` fetch+lưu (lệnh `fap subjects`). `label()`/`name()`/`credit_of()` tự nạp cache, **degrade êm về mã trơ / 0 tín chỉ** khi chưa cache → mọi nơi gọi đều an toàn. Đây là lớp join để API mã-trơ hiện **tên môn** + cấp **tín chỉ** cho GPA theo trọng số.

**grades.py** — `fetch_marks()` (GetStudentMark). `_gpa()` = TB cộng môn đã có điểm; `term_gpa()` → `(gpa, weighted)`: có tín chỉ (subjects đã cache) thì tính **theo trọng số tín chỉ**, không thì rơi về TB cộng. `_components()`/`_normalize_components()` (GetMarkByCourse): nhận cả list lẫn dict. `fetch_components()` trả `None` khi lấy hỏng. `detail_text()` render điểm thành phần + **tên môn** ở tiêu đề + dòng dự đoán "cần X/10 để qua" (qua `whatif.predict_course`, import trễ tránh vòng). **HỢP NHẤT** `GetStudentMark` với `courses.course_id_map()` (GetCourseOfSemester) → môn bị `GetStudentMark` bỏ sót / thiếu `courseID` vẫn lấy được điểm thành phần; endpoint lỗi/404 → cmap rỗng → giữ nguyên hành vi cũ.

**courses.py** — lớp đăng ký trong kỳ (GetCourseOfSemester). `fetch_courses()` trả `None` khi 404/lỗi (phân biệt rỗng-thật). `course_id_map()` THUẦN → `{mã: courseId}` (vá điểm thành phần). `roster()`/`roster_from_activity()` THUẦN → 1 dòng/môn (môn/lớp/GV/phòng); `courses_text()` ưu tiên GetCourseOfSemester, **fallback gộp từ GetActivityStudent** nếu endpoint không dùng được. Mọi field dò đa-biến-thể (`courseId`/`courseID`/`CourseId`…).

**attendance.py** — `_pct()` trả `None` nếu CHƯA có dữ liệu (khác 0% thật). `_at_risk()` = `pct < 80%`. `banrisk()` trả exit code 2 nếu có nguy cơ (tiện cron). `report()` hiện thêm **tên môn** (subjects).

**transcript.py** — `_weighted_gpa()` = Σ(điểm×tín chỉ)/Σ(tín chỉ) — **GPA chính thức theo tín chỉ** (nguồn AcademicTranscript). `gpa_text()` gộp toàn khoá + từng kỳ.

**whatif.py** — `_split()` tách môn đã/chưa có điểm. `needed_average(target,…)` cho mô phỏng GPA cả kỳ. `predict_course(components,target)` THUẦN: từ trọng số+giá trị các đầu điểm 1 môn → "cần TB bao nhiêu ở phần còn lại để **qua môn**" (trọng số tự triệt tiêu nên không cần biết %/phân số); `predict_line()` render 1 dòng. `run()` in bảng dự kiến (5–10) hoặc điểm-cần.

**extras.py** — `campuses()` (GetAllActiveCampus, KHÔNG cần token — chọn campus trước login), `exams_text()`/`exams_ics()` (lịch thi → `.ics` + nhắc trước 1 ngày, parse ngày/giờ generic), `notifications_text()` (GetNotificationByRoll, mới nhất trước), `news()`, `fees()`.

**extract.py** — `fap extract` dump A) RKStorage (nếu có) B) ~21 endpoint read-only C) `getCourseAttendance` từng môn D) `GetMarkByCourse` từng môn E) `GetWeekByDate`→`GetActivityStudentByWeek`. Giãn cách `FAP_EXTRACT_DELAY` giây giữa lượt.

---

## 5. Logic tầng giao tiếp · `app/`

**bot_core.py** — `handle(cmd, arg)` là **lõi chung của bot + web + notify**: chuẩn hoá lệnh (gồm `_`→`-`, để tên menu `grades_detail` khớp `grades-detail`), `creds()`+`current_semester()` một lần, route tới `_*_text()`. Bọc `try/except SystemExit` → token hết hạn trả **lời nhắn** thay vì sập bot/web. `all_text()` lấy marks/att **đúng 1 lần** rồi chia sẻ (không gọi trùng endpoint). `COMMAND_INFO` là **nguồn lệnh duy nhất** → suy ra `COMMANDS` + `menu_commands()` (cấp cho menu gợi ý Telegram & slash Discord).

**notify.py** — `push()` gửi Telegram + Discord (kiểm HTTP status — `requests.post` không raise với 4xx; xử lý 429 Retry-After). `push_new_notifications()` chỉ đẩy thông báo MỚI (dedupe theo `id`, sentinel `None`=chưa baseline; bỏ qua khi fetch rỗng; file hỏng → cô lập `.corrupt` + rebaseline).

**dashboard.py** — `status()` (hôm nay + GPA tạm tính + điểm danh + cảnh báo cấm thi), `week()` (lọc từ kỳ), `week_exact()` (GetActivityStudentByWeek — chuẩn cho tuần nghỉ lễ; render generic, group theo ngày).

**attendwatch.py / gradewatch.py** — kiến trúc giống nhau: `compute()` là **lõi THUẦN** (không mạng/IO, test offline được) so trạng thái với lần trước → sự kiện mới; `poll()` gọi mạng + lưu `output/*_state.json` (ghi atomic, file hỏng → `.corrupt`); `loop()` chạy nền (khung giờ 06–22, **tự refresh token ~50'** để service sống lâu). Chống spam: mỗi buổi/điểm chỉ báo 1 lần; so điểm theo **số** (`8.5`≡`8.50`); fetch hỏng → giữ mốc cũ (không nuốt sự kiện).

**webui.py** — `http.server` stdlib, **CHỈ bind 127.0.0.1**. Trang 1 file: nút nhóm theo chủ đề → `GET /q?c=<lệnh>` → `handle()`; `/me` lấy tên/MSSV từ token.json cho header. Tự bật `FAP_CACHE_MIN=2` (bấm nhiều không gọi lại API). Responsive + sáng/tối tự động + tự-làm-mới 60s.

**telegrambot.py / discordbot.py** — long-poll/gateway, gọi `handle()` trong thread executor (không chặn loop). **Chỉ trả lời chủ tài khoản** (Telegram `TELEGRAM_CHAT` bắt buộc; Discord `DISCORD_ALLOWED_USER_ID` bắt buộc, mở cho mọi người phải cố ý `DISCORD_ALLOW_ANYONE=1`). Lúc khởi động **tự đăng ký menu lệnh gợi ý**: Telegram `setMyCommands` (nút Menu ☰ + gợi ý khi gõ `/`); Discord `app_commands` slash (`tree.sync()` toàn cục, bọc try/except → thiếu thì vẫn chạy prefix `!`). Cả hai không sống-còn: lỗi đăng ký menu thì bot vẫn chạy.

**reminders.py** — **nhắc trước mỗi tiết** cho bot tương tác. Lõi THUẦN `due_reminders(sessions, now, lead, sent)` (tiết bắt đầu trong `[now, now+lead]` & chưa nhắc) + `reminder_text()` → test offline. `ClassReminder.tick()` lo phần mạng: nạp TKB hôm nay (cache ~3h, reset `sent` khi sang ngày), **tự refresh token ~50'** (vá việc bot tương tác trước đây không refresh → chết token sau ~1h). Telegram tick mỗi vòng long-poll; Discord chạy task nền 60s và **DM** chủ tài khoản. `FAP_REMIND_MINUTES=0` → tắt.

**gcal.py** — đẩy `.ics` lên Google Calendar (OAuth riêng, upsert chống trùng theo `iCalUID`).

---

## 6. Shared

- **config.py** — nạp `.env` (strip quote, không hỗ trợ comment cuối dòng), phơi `TELEGRAM_*`, `DISCORD_*`, `GCAL_*`, `FAP_*`.
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

- **Test**: `python tests/test_logic.py` (50 unit, logic thuần) + `python tests/integration_offline.py` (77 integration, mock mạng) — hoặc gói gọn: **`fap selftest`**. Cả hai KHÔNG cần token/mạng.
- **Bảo mật**: token nằm trong query `Authen` (lỗi mạng không in URL); `output/`, `.env`, `credentials.json`, `device-data/` đều `.gitignore`; web chỉ localhost; bot khoá theo chủ tài khoản; chỉ thao tác tài khoản của chính bạn (xem [SECURITY.md](../SECURITY.md)).
