# 21 · API v2 của myFAP (opt-in, thử nghiệm) · myFAP API v2 (opt-in, experimental)

**VI —** Từ **myFAP 2.0.5 (versionCode 29)**, app có thêm một **API v2** chạy qua máy chủ `fap-proxy.fpt.edu.vn`, bật/tắt bằng **một cờ phía server**. fap-cli **mặc định vẫn dùng v1** (`api.fpt.edu.vn/fap/api/MyFAP/…`) và **v1 không đổi** ở 2.0.5. fap-cli đã có **client v2 OPT-IN, THỬ NGHIỆM, CHƯA kiểm chứng với server thật** — bật bằng `FAP_API_VERSION=v2` (xem **§5**). Mọi điều dưới đây đọc từ **mã của chính app** (bundle Hermes), qua công cụ có che dữ liệu — fap-cli **chưa gọi v2 thật lần nào**.
**EN —** Since **myFAP 2.0.5 (versionCode 29)** the app ships an **API v2** served via `fap-proxy.fpt.edu.vn`, switched by **a server-side flag**. fap-cli **still uses v1 by default**, which is **unchanged** in 2.0.5. fap-cli now has an **OPT-IN, EXPERIMENTAL v2 client that has NOT been verified against the live server** — enable it with `FAP_API_VERSION=v2` (see **§5**). Everything here was read from the **app's own code** through a masking tool — fap-cli has **never called v2 for real**.

> 🔒 **VI —** **Không** ghi khoá ký (HMAC key) v2, **không** ghi bearer tĩnh nhúng trong app. Quyết định: fap-cli **KHÔNG nhúng** khoá v2 (khác tiền lệ `SECRET` của v1) — bạn tự trích từ **APK của chính bạn** vào `.env` (§5). Bearer tĩnh **không bao giờ** được dùng.
> 🔒 **EN —** The v2 signing key and the app's embedded static bearer are **not** recorded here. Decision: fap-cli does **NOT embed** the v2 key (unlike v1's `SECRET`) — you extract it from **your own APK** into `.env` (§5). The static bearer is **never** used.

---

## 1. App chọn v1 hay v2 thế nào · How the app picks v1 or v2

| | |
|---|---|
| Mặc định · Default | `v1` |
| Khi nào đổi · When | Mỗi lần **mở app** (splash) gọi `MyFAP/GetApiActive` trên `fap-proxy`. Chỉ khi `code == 200 && data === true` mới chuyển **toàn bộ app** sang v2; lỗi gì cũng **giữ v1**. Không có nút cho người dùng, không có remote-config khác. · On every cold start; switches the **whole app** only on `code 200 && data === true`; any error keeps v1 |
| Phiên gắn phiên bản · Version-pinned session | Lúc đăng nhập app lưu `sessionApiVersion`; nếu lệch phiên bản hiện tại thì **đăng xuất** bắt đăng nhập lại ⇒ ngày FPT bật v2, mọi người dùng app bị đá ra một lần. Token v1 có dùng được trên v2 không: **chưa kiểm chứng**. |
| Hiện tại · Today | **Không biết cờ đang bật hay tắt** — không gọi mạng để kiểm. |

---

## 2. Một request v2 · A v2 request

| | v1 (fap-cli đang dùng · current) | v2 |
|---|---|---|
| URL | `https://api.fpt.edu.vn/fap/api/MyFAP/<Name>` | `https://fap-proxy.fpt.edu.vn/MyFAP/<Name>` (không có `/fap/api`) |
| Token | tham số query `Authen` | header `Authorization: Bearer <token>` — **riêng 7 endpoint vẫn gửi thêm `Authen` trên query**: CheckUpdateProfile, GetSemesterMark, GetApplication, CheckOpenFeedBack, GetNotificationByRoll, GetNotificationByDonor, AddRate (nên việc che token trong log vẫn cần) |
| Checksum | query `checksum=` = HMAC-SHA1 theo **giờ VN** (retry ±1h) | header `Checksum: <sig>:<ts>`; `sig` = HMAC-SHA256 trên `(token \| hằng mặc định) + "MyFAP" + <epoch giây>`, Base64, rồi `=`→`%3d`, khoảng trắng→`+`. Khoá là chuỗi hex nhúng trong app, dùng **nguyên chuỗi làm byte UTF-8** (không hex-decode). **Không còn cửa sổ giờ** ⇒ không cần retry ±1h; chữ ký **không** phủ mã SV/campus/path |
| Header khác | `User-Agent: okhttp/4.9.2` | `ClientCode: MyFAP`, `CampusCode: <mã>`, `Content-Type: application/json`; timeout 15 s |
| Method | GET (trừ đăng nhập) | GET; **POST** cho `AuthenticationByFeId`, `AuthenticationByGoogleAccessToken`, `AddRate`, `SubmitStudentFeedback`. `UpdateTokedevices` / `UpdateTokenDonor` là **ghi** nhưng đi bằng GET |
| Tham số | `campusCode` thường | đa số đổi thành `CampusCode` hoa; ngoại lệ: `GetWeekByDate` chỉ `{date}`, `GetTokenWithEmp` chỉ `{RollNumber}`, `GetSemester`/`GetVersion` không tham số, `GetCourseOfSemester`/`GetDiemphongtrao` giữ `semester` thường |
| Đăng nhập | `AuthenticationByFeId?campusCode&checksum` + body `{token}` | POST body `{token: <access token FE>}` — chính token FE đó làm Bearer **và** khoá checksum; không `campusCode`/`checksum` trên query |

**Gọi không cần đăng nhập · No-auth calls** (`GetApiActive`, `GetAllActiveCampus`): app gửi header cố định với `CampusCode: HN` và một **bearer tĩnh nhúng trong app** (không phải của người dùng). fap-cli **không** dùng cách này (không mượn danh tính app).

### Lỗi phiên · Error contract

App coi là **hết phiên** khi body `code == '401'` **hoặc** `errorMessage === 'Unauthorized'` **hoặc** HTTP 401/500 (chỉ khi call có token và không phải bước đăng nhập) → xoá token, đăng xuất. Lỗi khác: GET trả `[]`, POST trả `null`.

> ✅ **VI — Đã vá lỗ hổng im lặng:** trước đây `check_auth` chỉ nhận HTTP 401/403 và `code '201'`, nên phản hồi kiểu v2 (`code '401'` / `'Unauthorized'` trong HTTP 200) thành **danh sách rỗng, không báo lỗi**. Giờ `check_auth` (và hàm thuần `is_session_expired` cho watcher) nhận cả hai dấu hiệu đó → cùng thông điệp "token hết hạn → `fap refresh` / `/login`". **HTTP 500 cố ý KHÔNG tính** là hết phiên (khác app) để không tạo vòng refresh khi server trục trặc. Xem [16-troubleshooting](16-troubleshooting.md).
> ✅ **EN — Silent gap closed:** `check_auth` used to recognise only HTTP 401/403 and `code '201'`, so a v2-style body inside HTTP 200 became an empty list with no error. It (and the pure `is_session_expired` for watchers) now also recognises both v2 markers → the same "token expired → `fap refresh` / `/login`" message. **HTTP 500 is deliberately NOT** treated as expired (unlike the app) to avoid refresh loops while the server is unhealthy.

---

## 3. Danh sách endpoint · Endpoint registry

**VI —** v1 trong 2.0.5: **37 endpoint `MyFAP/…` + `GetRequiredSurvey`** — y hệt 2.0.4. v2 có sổ riêng **39 đường dẫn**:
**EN —** v1 in 2.0.5: the same **37 + `GetRequiredSurvey`** as 2.0.4. v2 has its own registry of **39 paths**:

| So với v1 · vs v1 | Endpoint |
|---|---|
| ➕ Thêm · Added | `GetApiActive`, `GetStudentFeedbacks`, `GetStudentFeedbackForm`, `SubmitStudentFeedback` (**GHI — không bao giờ gọi**) |
| ➖ Bỏ · Dropped | `AuthenticationByUsername`, `GetStudentRate` (v2 trả `[]` cố định) |
| 🔤 Đổi hoa/thường · Casing | `getCourseAttendance` → `GetCourseAttendance` (v1 vẫn viết thường — fap-cli khớp) |

Bộ **feedback** chỉ có trên v2 và **chưa màn hình nào gọi** ⇒ chưa biết schema phản hồi. `GetRequiredSurvey` vẫn ở `survey.fpt.edu.vn`, không qua proxy.

---

## 4. fap-cli nên làm gì · What fap-cli should do

| Tình huống · Situation | Hành động · Action |
|---|---|
| **Hôm nay** (v1 chạy) · Today | Không phải sửa gì — mọi hằng số fap-cli dựa vào (SECRET, BASE, CLIENT_ID, ISSUER, REDIRECT_URI) **giữ nguyên** ở 2.0.5 |
| FPT bật v2 nhưng v1 vẫn phục vụ · v2 on, v1 still served | fap-cli vẫn chạy. Người dùng app bị đá ra một lần (không liên quan fap-cli) |
| **v1 bị tắt** · v1 turned off | ✅ **Đã có client v2 opt-in · Opt-in v2 client exists** (§5, `fapc/core/apiv2.py`): host mới, header ký HMAC-SHA256 theo epoch giây, bảng tham số cho **mọi** endpoint fap-cli gọi, `GetCourseAttendance` hoa, đăng nhập POST `{token}`, `api_version` trong `token.json` (lệch ⇒ `fap refresh`), `check_auth` hiểu lỗi v2 (§2 "Lỗi phiên"). Khoá v2 **không nhúng** — người dùng tự trích từ APK của mình. **Chưa kiểm chứng thật** ⇒ chỉ bật khi v1 thật sự hỏng · **not verified live** ⇒ switch only when v1 is really broken |
| Phát hiện sớm · Early warning | ✅ **Đã làm · Done.** Hàm THUẦN `classify_drift(http, body, content_type)` trong `fapc/core/api.py` soi chính phản hồi v1 (**không thêm request nào**): 301/302/303/307/308 → `redirect`, 410 → `gone`, 404 mà thân **không phải JSON** → `not_found`. 404 kèm JSON (`GeFeeByRoll`…) và 404 của endpoint vốn đã 404 (`GetSemesterMark`, `GetVersion`, `GetCourseOfSemester`) **không** tính. Tín hiệu đầu tiên của mỗi tiến trình in **một** gợi ý song ngữ ra `stderr` ("FAP có thể đã chuyển sang API v2 — xem tài liệu này và `FAP_API_VERSION`"), chỉ ghi tên endpoint + mã HTTP, **không** URL/token. Thân lỗi phiên kiểu v2 thì do `check_auth` lo (báo "token hết hạn"). · Pure classifier on the v1 reply, zero extra requests; first signal per process prints one bilingual stderr hint (endpoint + HTTP code only). Troubleshooting: [16-troubleshooting](16-troubleshooting.md) |

> 🧭 **VI —** Từ 2.0.5 app tự cập nhật **JS qua OTA** (máy chủ của bên phát triển app, không phải `fpt.edu.vn`), có cả bản **bắt buộc**. Endpoint, trường và ánh xạ có thể đổi **mà không tăng versionCode** — xem cách theo dõi ở [20-api-fields](20-api-fields.md) §5.
> 🧭 **EN —** Since 2.0.5 the app updates its **JS over the air** (the app vendor's server, not `fpt.edu.vn`), including **mandatory** updates. Endpoints, fields and mappings can change **without a new versionCode** — see [20-api-fields](20-api-fields.md) §5.

---

## 5. Bật API v2 (thử nghiệm) · Enabling API v2 (experimental)

> ⚠️ **VI —** **Opt-in, thử nghiệm, CHƯA kiểm chứng với server thật.** Mặc định là `v1` và hành vi v1 **y hệt** trước đây. Chỉ bật khi v1 thật sự hỏng (gợi ý "FAP có thể đã chuyển sang API v2" lặp lại ở nhiều lệnh — [16-troubleshooting](16-troubleshooting.md)).
> ⚠️ **EN —** **Opt-in, experimental, NOT verified against the live server.** The default is `v1` and v1 behaves **exactly** as before. Switch only when v1 is really broken (the "FAP may have moved to API v2" hint repeats across commands).

### 5.1 Các bước · Steps

1. **VI —** Lấy khoá ký v2 từ **chính bản APK myFAP chính thức của bạn** (lệnh ghi thẳng `FAP_V2_KEY=…` vào `.env`, **không in giá trị** ra màn hình): · **EN —** Extract the v2 signing key from **your own copy of the official myFAP APK** (the command writes `FAP_V2_KEY=…` straight into `.env` and **never prints the value**):
   ```bash
   python analysis/apk_drift.py --write-v2-key <myfap.apk>
   ```
2. **VI —** Thêm vào `.env` (không có chú thích `#` cùng dòng — bộ đọc `.env` không hỗ trợ): · **EN —** Add to `.env` (no inline `#` comments — the `.env` reader doesn't support them):
   ```dotenv
   FAP_API_VERSION=v2
   ```
3. **VI —** Đổi token theo v2: `fap refresh` (hoặc `/login` trong bot). Token cũ mang dấu v1 ⇒ mọi lệnh dữ liệu sẽ dừng với thông báo "bạn vừa đổi phiên bản API — chạy `fap refresh`" cho tới khi đổi xong. Máy `FAP_TOKEN_READONLY=1` không refresh được: đổi `FAP_API_VERSION` **cùng lúc** với máy chủ rồi chép lại `token.json` sau khi máy chủ refresh. · **EN —** Re-exchange the token for v2: `fap refresh` (or `/login` in the bot). Until then every data command stops with "you switched API versions — run `fap refresh`". A `FAP_TOKEN_READONLY=1` box can't refresh: switch `FAP_API_VERSION` **together** with the owner box and copy `token.json` again after the owner refreshes.
4. **VI —** Khởi động lại service thường trú (bot/watcher) để nạp `.env` mới — watcher tự refresh ~50' cũng sẽ đổi token theo phiên bản đang cấu hình. · **EN —** Restart resident services (bots/watchers) so they load the new `.env`; their ~50-min self-refresh also re-exchanges for the configured version.

**Quay về v1 · Switch back:** **VI —** xoá dòng `FAP_API_VERSION` (hoặc đặt `v1`), chạy `fap refresh`, khởi động lại service. Có thể để nguyên `FAP_V2_KEY` (v1 không đọc nó). · **EN —** remove `FAP_API_VERSION` (or set `v1`), run `fap refresh`, restart services. `FAP_V2_KEY` may stay (v1 never reads it).

### 5.2 Quy tắc giữ khoá · Key-handling rules

- **VI —** `FAP_V2_KEY` là **bí mật**: chỉ nằm trong `.env` (đã gitignore) hoặc biến môi trường; **không commit**, **không dán vào chat/issue**. fap-cli chỉ dùng nó để tính HMAC; khoá **không** nằm trong URL, header, log, thông báo lỗi hay `token.json` (có test chặn). · **EN —** `FAP_V2_KEY` is a **secret**: `.env` (gitignored) or the environment only; **never commit** it, never paste it into chats/issues. fap-cli only uses it to compute the HMAC; it never appears in URLs, headers, logs, error messages or `token.json` (enforced by tests).
- **VI —** Mỗi người tự trích từ APK **của mình**; dự án không phát hành khoá. Profile (`FAP_PROFILE`) **thừa kế** `FAP_V2_KEY`/`FAP_API_VERSION` từ `.env` gốc (không phải khoá danh tính); muốn khác thì đặt trong `.env.<profile>`. · **EN —** Everyone extracts it from **their own** APK; the project never distributes it. Profiles **inherit** `FAP_V2_KEY`/`FAP_API_VERSION` from the root `.env` (not identity keys); override in `.env.<profile>`.
- **VI —** Giá trị `FAP_API_VERSION` lạ (không phải `v1`/`v2`) ⇒ dùng **v1** + **một** cảnh báo song ngữ (không in lại giá trị). Chọn `v2` mà thiếu khoá ⇒ dừng với hướng dẫn trích khoá, **không gửi request nào**. · **EN —** An unknown `FAP_API_VERSION` ⇒ **v1** plus **one** bilingual warning (the value is not echoed). `v2` without a key ⇒ stops with extraction instructions, **zero requests**.

### 5.3 fap-cli làm gì khi bật v2 · What fap-cli does on v2

| | |
|---|---|
| Request | `GET https://fap-proxy.fpt.edu.vn/MyFAP/<Name>?<params>` · header `ClientCode: MyFAP`, `CampusCode`, `Authorization: Bearer <token>`, `Checksum: <sig>:<epoch>`, `Content-Type: application/json` · timeout 15 s · **không** theo redirect · **không** thử lại ±1h (ký theo epoch giây) |
| Đăng nhập · Login | `POST …/MyFAP/AuthenticationByFeId`, body `{"token": <access token FE>}`, ký bằng **chính** token FE; `token.json` được đóng dấu `"api_version"` (cả v1 lẫn v2). Token cũ không có dấu = `v1` |
| Phiên lệch · Mismatch | `api_version` trong `token.json` ≠ `FAP_API_VERSION` ⇒ `SystemExit` "chạy `fap refresh`" (giống app: lệch `sessionApiVersion` ⇒ đăng xuất). `fap refresh`, watcher tự refresh, `/login` của bot đều đổi lại theo phiên bản đang cấu hình |
| Luôn v1 · Always v1 | `GetAllActiveCampus` (`fap campuses`): app gọi bản v2 bằng **bearer tĩnh của app** — fap-cli không mượn danh tính đó, nên lệnh này vẫn đi v1 và **không cần token** |
| Bỏ qua · Skipped | `GetStudentRate`: adapter v2 của app trả `[]` **cố định** (không có request) ⇒ `fap extract` bỏ qua, in ghi chú |
| Cấm · Denied | `AddRate`, `SubmitStudentFeedback`, `UpdateTokedevices`, `UpdateTokenDonor` (GHI) và `GetApiActive` (cần bearer tĩnh) — bị từ chối **trước khi** chạm mạng |
| Lỗi/cache · Errors/cache | Cùng hợp đồng `(http, body)` với v1, cùng `check_auth`/`is_session_expired`, cùng cache `FAP_CACHE_MIN` (khoá tách riêng `v2|…`). Lỗi mạng không in URL/token/khoá |

**Bảng endpoint (đọc từ adapter v2 của app) · Endpoint table (read from the app's v2 adapters)** — mọi endpoint là GET · all GET:

| fap-cli gọi · v1 name | v2 path | Tham số query (đúng thứ tự app) · query params |
|---|---|---|
| `GetStudentById` | `GetStudentById` | `rollNumber, CampusCode` |
| `CheckUpdateProfile` | `CheckUpdateProfile` | `CampusCode, rollNumber, Authen` |
| `GetSemester` | `GetSemester` | *(không · none)* |
| `GetSubjets` | `GetSubjets` | `CampusCode` |
| `GetSubjectBySemester` | `GetSubjectBySemester` | `CampusCode, Semester` |
| `GetCourseOfSemester` | `GetCourseOfSemester` | `CampusCode, semester, rollNumber` |
| `GetStudentMark` | `GetStudentMark` | `CampusCode, rollNumber, Semester` |
| `GetSemesterMark` | `GetSemesterMark` | `CampusCode, rollNumber, Authen` |
| `GetMarkByCourse` | `GetMarkByCourse` | `CampusCode, CourseId, rollNumber` *(app v2 không gửi `SubjectCode`)* |
| `AcademicTranscript` | `AcademicTranscript` | `CampusCode, rollNumber` |
| `GetDiemphongtrao` | `GetDiemphongtrao` | `CampusCode, rollNumber, semester` |
| `GetActivityStudent` | `GetActivityStudent` | `CampusCode, rollNumber, Semester` |
| `GetActivityStudentByWeek` | `GetActivityStudentByWeek` | `CampusCode, week, rollNumber, Semester, year` |
| `GetScheduleExam` | `GetScheduleExam` | `CampusCode, rollNumber, Semester` |
| `GetWeekByDate` | `GetWeekByDate` | `date` |
| `GetStudentAttendances` | `GetStudentAttendances` | `CampusCode, Semester, rollNumber` |
| `getCourseAttendance` | **`GetCourseAttendance`** | `CampusCode, rollNumber, Semester, SubjectCode, ClassName` |
| `GeFeeByRoll` | `GeFeeByRoll` | `CampusCode, rollNumber` |
| `GetBalance` | `GetBalance` | `CampusCode, rollNumber` |
| `GetTop10News` | `GetTop10News` | `CampusCode, type` |
| `SearchNews` | `SearchNews` | `CampusCode, type, keysearch` |
| `GetApplication` | `GetApplication` | `CampusCode, rollNumber, Authen` |
| `CheckOpenFeedBack` | `CheckOpenFeedBack` | `CampusCode, rollNumber, Authen` |
| `GetNotificationByRoll` | `GetNotificationByRoll` | `CampusCode, rollNumber, Authen` |
| `GetCampusInfo` | `GetCampusInfo` | `CampusCode, rollNumber` |

### 5.4 Chưa kiểm chứng / lệch app · Unverified / deviations

- **VI —** Toàn bộ v2 **chưa gọi thật**: chưa biết server có chấp nhận chữ ký/tham số đúng như trên, token v1 có dùng được cho v2 không, hay phản hồi đăng nhập v2 có cùng dạng `{code, data:{authenKey, rollnumber, …}}` như v1 (fap-cli giả định giống — app đọc cùng tên trường). · **EN —** Nothing on v2 has been called for real: unknown whether the server accepts the signature/params above, whether v1 tokens work on v2, or whether the v2 login reply has v1's `{code, data:{authenKey, rollnumber, …}}` shape (assumed — the app reads the same field names).
- **VI —** fap-cli ký **mọi** request v2 bằng Bearer + Checksum của **chính token bạn**; chưa kiểm chứng server chấp nhận đúng như vậy cho từng endpoint. · **EN —** fap-cli signs **every** v2 request with **your own** token's Bearer + Checksum; whether the server accepts that for every endpoint is unverified.
- **VI —** fap-cli thêm `User-Agent: okhttp/4.9.2` (như v1; app React Native trên Android cũng chạy qua OkHttp). · **EN —** fap-cli adds `User-Agent: okhttp/4.9.2` (as on v1; the RN app on Android also goes through OkHttp).

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
