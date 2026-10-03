# 21 · API v2 của myFAP (chưa dùng) · myFAP API v2 (not used yet)

**VI —** Từ **myFAP 2.0.5 (versionCode 29)**, app có thêm một **API v2** chạy qua máy chủ `fap-proxy.fpt.edu.vn`, bật/tắt bằng **một cờ phía server**. fap-cli **vẫn dùng v1** (`api.fpt.edu.vn/fap/api/MyFAP/…`) và **v1 không đổi** ở 2.0.5. File này ghi lại v2 để: (1) nhận ra nhanh nếu FPT chuyển hẳn sang v2 / tắt v1, (2) có sẵn đặc tả khi cần chuyển. Mọi điều dưới đây đọc từ **mã của chính app** (bundle Hermes), qua công cụ có che dữ liệu — chưa gọi thử v2 lần nào.
**EN —** Since **myFAP 2.0.5 (versionCode 29)** the app ships an **API v2** served via `fap-proxy.fpt.edu.vn`, switched by **a server-side flag**. fap-cli **still uses v1**, which is **unchanged** in 2.0.5. This file documents v2 so we can (1) notice quickly if FPT moves to v2 or turns v1 off, and (2) have a ready spec if we must migrate. Everything here was read from the **app's own code** through a masking tool — v2 has never been called.

> 🔒 **VI —** **Không** ghi khoá ký (HMAC key) v2, **không** ghi bearer tĩnh nhúng trong app. Cả hai nằm trong APK; nếu một ngày cần thì người bảo trì tự quyết định có nhúng hay không (giống tiền lệ `SECRET` của v1).
> 🔒 **EN —** The v2 signing key and the app's embedded static bearer are **not** recorded here. Both live in the APK; embedding them is a maintainer decision if it is ever needed.

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

> ⚠️ **VI — Lỗ hổng im lặng của fap-cli nếu gặp v2:** `check_auth` hiện chỉ nhận HTTP 401/403 và `code '201'`. Một phản hồi kiểu v2 (`code '401'` / `'Unauthorized'` trong HTTP 200) sẽ thành **danh sách rỗng, không báo lỗi**.
> ⚠️ **EN — fap-cli silent gap:** `check_auth` only recognises HTTP 401/403 and `code '201'`; a v2-style body inside HTTP 200 would become an empty list with no error.

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
| **v1 bị tắt** · v1 turned off | Cần client v2: host mới, header ký HMAC-SHA256 theo epoch giây, bảng tham số §2, `GetCourseAttendance` hoa, đăng nhập POST `{token}`, lưu `api_version` trong `token.json` (lệch thì bắt đăng nhập lại), `check_auth` hiểu lỗi v2, và nhúng khoá v2 (quyết định của người bảo trì) |
| Phát hiện sớm · Early warning | Một bộ phân loại THUẦN trên phản hồi v1 (404/410/30x/HTML/thân kiểu v2) → gợi ý "FAP có thể đã chuyển sang API v2" — **không thêm request nào** |

> 🧭 **VI —** Từ 2.0.5 app tự cập nhật **JS qua OTA** (máy chủ của bên phát triển app, không phải `fpt.edu.vn`), có cả bản **bắt buộc**. Endpoint, trường và ánh xạ có thể đổi **mà không tăng versionCode** — xem cách theo dõi ở [20-api-fields](20-api-fields.md) §5.
> 🧭 **EN —** Since 2.0.5 the app updates its **JS over the air** (the app vendor's server, not `fpt.edu.vn`), including **mandatory** updates. Endpoints, fields and mappings can change **without a new versionCode** — see [20-api-fields](20-api-fields.md) §5.

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
