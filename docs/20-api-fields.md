# 20 · Bản đồ trường API · API field map

**VI —** Ý nghĩa **đã kiểm chứng** của các trường trong phản hồi FAP mobile API, trường nào fap-cli đang dùng, trường nào chưa dùng và vì sao. Kèm cách **kiểm lại an toàn** sau mỗi lần FAP cập nhật app. Đọc file này **trước** khi thêm tính năng đọc một trường mới — vài trường không giống tên của chúng.
**EN —** The **verified** meaning of FAP mobile API response fields, which ones fap-cli uses, which it doesn't and why, plus a **safe re-audit** procedure for when FAP updates its app. Read this **before** building on a new field — several fields are not what their names say.

> **VI —** Danh sách endpoint + tham số + checksum: [01-reverse-engineering](01-reverse-engineering.md) · [03-extraction-catalog](03-extraction-catalog.md) · [05-checksum-map](05-checksum-map.md). File này nói về **trường bên trong phản hồi**.
> **EN —** Endpoints, parameters and checksums live in [01](01-reverse-engineering.md) · [03](03-extraction-catalog.md) · [05](05-checksum-map.md). This file is about the **fields inside responses**.

---

## 0. Kiểm chứng bằng cách nào · How these facts were verified

| Nguồn · Source | Dùng cho · Used for |
|---|---|
| **Hàm của app chính thức** trong bundle Hermes (myFAP 2.0.4, versionCode 26) — vd `getAttendanceStatus`, `getStatusConfig` · **Official app functions** in the Hermes bundle | Ý nghĩa của **mã trạng thái** — không đoán · the meaning of **status codes**, never guessed |
| **Dump phản hồi thật** của chính tài khoản mình (`fap extract` → `output/api/`), chỉ đo **số đếm / hình dạng** · **Real responses** from your own account, measured as **counts / shapes only** | Trường nào có thật, rỗng bao nhiêu, định dạng ra sao · which fields exist, how often they are empty, what shape they have |
| Đối chiếu chéo giữa 2 endpoint · Cross-checks between endpoints | Vd số buổi P/A theo môn (lịch) **khớp đúng** `numberOfTakenAttendances` (điểm danh) · e.g. per-subject P/A counts matched `numberOfTakenAttendances` exactly |

> 🔒 **VI —** Chưa từng in **giá trị** nào ra: chỉ tên khoá, kiểu, tỉ lệ có giá trị và số đếm. Bundle app có **dữ liệu cá nhân của người khác** nướng sẵn bên trong — file disassembly (`analysis/disasm.hasm`, `analysis/strings_clean.txt`, bundle) **luôn gitignore**, không bao giờ commit, và khi tra cứu chỉ in chuỗi dạng định danh/nhãn (che mọi thứ có chữ số, `@`, token). Xem §5.
> 🔒 **EN —** No **value** was ever printed: only key names, kinds, fill ratios and counts. The app bundle has **someone else's personal data** baked in, so the disassembly files are **always gitignored**, never committed, and lookups print only identifier/label-shaped strings (anything with digits, `@` or token shape is masked). See §5.

---

## 1. Trường "không giống tên" · Fields that are not what their names say

| Endpoint · Trường | Thực tế · Reality | fap-cli xử lý · How fap-cli handles it |
|---|---|---|
| `GetActivityStudent.meetURL` | **Không phải URL** — là **mã phòng Google Meet trần** `abc-defg-hij` (28/28 giá trị khớp mẫu 3-4-3, 0 giá trị bắt đầu bằng `http`). Có mặt ở mọi buổi nhưng phần lớn là `""`. Mỗi lớp (môn + nhóm) có **đúng 1 mã**, nhưng FAP chỉ gắn vào **vài buổi** — và gắn cả buổi **học tại phòng** (26/28). · **Not a URL**: a bare Meet room code; one per class, attached to only some sessions, in-person ones included. | `fmt.meet_url` ghép `https://meet.google.com/<mã>` khi **đúng** mẫu 3-4-3, **chỉ** cho buổi online. `schedule.fill_meet` cho buổi thiếu mã **mượn** mã của chính lớp đó (chỉ khi lớp có đúng 1 mã trên **cả kỳ**). Kết quả trên dump thật: 11/11 buổi online có link (2/11 nếu không mượn, 0/11 nếu chỉ nhận `http`). |
| `GetActivityStudent.isOnline` | Chuỗi `"true"` / `"false"` · a string | `fmt.is_online` (danh sách trắng) — **quyết định online bằng cờ này, không bằng việc có mã Meet** |
| `GetActivityStudent.attendanceStatus` | Mã **1 chữ**: `P` có mặt · `A` vắng · còn lại (thực tế `N`) = chưa diễn ra — theo hàm `getAttendanceStatus` của app. **Không có mã "muộn".** · One-letter code per the app's own function. | `attendance.session_status` / `att_tail`: ✅/❌ ở buổi đã qua; ngày vắng theo môn trong `/attendance` |
| `GetActivityStudent.date` | `"M/D/YYYY 12:00:00 AM"` (vd `9/14/2026 12:00:00 AM`) | `parse_session` / `parse_date` lấy phần trước dấu cách |
| `getCourseAttendance.attendanceStatus` | Chữ **đầy đủ**: `Present` / `Absent` / `Future` (khác endpoint lịch) · full words, unlike the schedule | Watcher điểm danh đọc bằng chữ; `session_status` nhận **cả hai** dạng |
| `GetApplication.studentStatus` | **Theo app 2.0.5** (`getStatusConfig` + i18n `lb_appli_status_*`): `"0"` đang xử lý · `"1"` đã được chấp nhận · `"2"` **Hủy** · `"3"` **Đang chờ thanh toán** · khác **"Khác"**. ⚠️ App 2.0.4 chỉ có nhánh 0/1, mọi mã khác rơi vào "Đã bị từ chối" ⇒ `"2"` **từng** bị hiển thị là "từ chối" — 2.0.5 sửa lại và bỏ hẳn nhãn đó · per the 2.0.5 app; 2.0.4 showed every other code as "rejected" | Huy hiệu ⏳ / ✅ / 🚫 / 💳; mã lạ hiện `❔ Khác (mã N)` (khớp nhãn "Khác" của app) |
| `GetNotificationByRoll.contents` | **Text thuần** có xuống dòng (0/19 có `<`), 77–888 ký tự · plain text with newlines | Chỉ bóc **thẻ HTML thật theo tên** (không phải `<[^>]+>` — sẽ xoá nhầm `<MSSV>`, `điểm < 5`, `->`). Trích 1 dòng ≤140 ký tự, không cắt giữa URL |
| `GetNotificationByRoll.id` | Số nguyên **2–3 chữ số, duy nhất**, thứ tự giảm dần = mới nhất trước · stable small int | Khoá `#id` cho `/notifications <id>` (KHÔNG dùng vị trí: đổi khi có tin mới, và Discord đánh số lại danh sách Markdown) |
| `GetNotificationByRoll.rollnumbers` | Có thể chứa **mã SV của người khác** (5/19 có giá trị) · may hold other students' roll numbers | **Không bao giờ hiển thị** |
| `GetStudentAttendances.startDate` / `endDate` | ISO `2026-05-11T00:00:00`; `endDate` là ngày học **cuối** | Giai đoạn môn (chưa bắt đầu / còn N ngày / đã kết thúc); môn chưa bắt đầu **không** bị báo nguy cơ cấm thi |
| `GetStudentAttendances.numberOfTakenAttendances` | Trên dump thật (100% có mặt) bằng đúng số buổi P/A — **chưa chứng minh** được khi có buổi vắng: có thể là "số buổi đã điểm danh" hoặc "số buổi có mặt" | **Cố ý không** dùng `== 0` để tắt cảnh báo: nếu nó đếm "có mặt", SV vắng hết sẽ mất cảnh báo |
| `CheckOpenFeedBack` / `CheckUpdateProfile` | `data` là **boolean trần**, không có `isOpen` / `hasUpdateProfile` (docs cũ ghi sai) | Chưa dùng (ứng viên — §3) |

---

## 2. Tổng quan dùng / chưa dùng · Used vs unused

**VI —** Audit 2026-09 (6 nhóm endpoint, mỗi nhóm 1 lượt tìm + 1 lượt đối chiếu đối kháng), **236** cặp (endpoint, trường) trên 30 endpoint đọc: **106 đang dùng · 130 chưa dùng** (59 đáng làm · 18 PII giữ nguyên · 22 id nội bộ · 13 trùng trường đã dùng · 18 chưa rõ). Sau đó đã đưa vào dùng: `meetURL` (link Meet), `attendanceStatus`, `studentStatus`, `contents`, `startDate`/`endDate`.
**EN —** The 2026-09 audit covered **236** (endpoint, field) pairs across 30 read endpoints: **106 used · 130 unused** (59 worth building · 18 PII to keep unused · 22 internal ids · 13 duplicates · 18 unclear). Since then these went into use: `meetURL`, `attendanceStatus`, `studentStatus`, `contents`, `startDate`/`endDate`.

---

## 3. Còn đáng làm · Still worth building

| Trường · Field | Có dữ liệu · Data | Tính năng · Feature | Công · Effort |
|---|---|---|---|
| `GetActivityStudent.material` | 81/81 (URL) | Link 📚 tài liệu môn trong `courses`, `.ics`, Google Calendar | S |
| `AcademicTranscript.gradeStatus` / `result` / `attempt` | dump rỗng (chưa có kỳ hoàn thành) | **Sửa lỗi đúng/sai**: `credits_text` + GPA đang coi mọi môn điểm > 0 là qua và cộng cả lần học lại | M — cần mẫu thật |
| `GetMarkByCourse` (HTML, phần `tfoot`: Average / Status) | không dump | Điểm TB + trạng thái **chính thức** cho các môn `GetStudentMark` bỏ sót (2/6 môn) | M |
| `CheckOpenFeedBack` + `GetStudentRate.hasStudentRated` | 1/1 | Báo "đợt feedback đang mở, còn N môn chưa đánh giá" (**không bao giờ** gọi `AddRate`) | S–M |
| `GetSubjets.replacedBy` | 334/1622 | "Môn đã được thay bằng X" khi trượt; `resolve()` nhận mã cũ | S |
| `GetSubjets.fee` | 1469/1622 | Học phí từng môn / ước tính học phí kỳ | S |
| `GetScheduleExam.examTime` (giờ kết thúc) | dump rỗng | `DTEND` thật trong `exams-ics` | S |
| `getCourseAttendance.isSeminar` | 81/81 | Tag 🎤 trong tin báo điểm danh | S |

---

## 4. Giữ nguyên không dùng · Keep unused (PII)

**VI —** Không bao giờ đưa vào chat/push: `GetStudentById` → `address`, `homePhone`, `dateOfIssue`, `placeOfIssue`, `nCode`, `placeOfWork`, `parentName`, `parentPhone`, `parentEmail`, `parentAddress`, `parentJob`; `GetNotificationByRoll.rollnumbers`; `GetApplication.fileUpLoad` (URL tệp đính kèm — có thể là ảnh CCCD/giấy khám); `GetApplication.description`; `GetStudentRate.rateComment` / `rateValue` (đánh giá kín về giảng viên có tên); `GetCampusInfo.contactName` / `mobile`.
**EN —** Never sent to chat/push: the `GetStudentById` personal fields above, notification `rollnumbers`, application attachments and descriptions, private lecturer ratings, a named staff member's contact details.

> ⚠️ **VI — Còn mở:** `/profile` hiện **đang** hiển thị `iDCard` (CCCD), `mobilePhone`, `dateOfBirth`, `email` và lệnh này đi qua bot ⇒ các trường đó tới máy chủ Telegram/Discord. Nên giới hạn ở CLI cục bộ.
> ⚠️ **EN — Open:** `/profile` currently **does** show national ID, phone, date of birth and email, and it is reachable from the bots, so those reach Telegram/Discord servers. They should be CLI-only.

---

## 5. Kiểm lại sau khi FAP cập nhật app · Re-audit after a FAP app update

**VI —**
1. **Có bản mới không?** `gplaydl info com.fuct` (môi trường conda `abc`, đăng nhập ẩn danh) — so `versionCode` với bản đã kiểm (xem §6).
2. **Trường phản hồi:** `fap extract` → `python analysis/keys_schema.py` — so với lần trước; chỉ in tên khoá / kiểu / tỉ lệ.
3. **Mã trạng thái / ánh xạ:** giải nén `assets/index.android.bundle` → `hbc-disassembler` → `.hasm` (**để ngoài repo hoặc trong các đường đã gitignore**). Tìm hàm theo tên (vd `getAttendanceStatus`, `getStatusConfig`), in thân hàm nhưng **che** mọi chuỗi không phải định danh/nhãn thuần chữ.
4. **Endpoint:** đối chiếu tập tên `MyFAP/…` với [01](01-reverse-engineering.md) §B — bản 2.0.4 có **37 MyFAP + GetRequiredSurvey = 38**, không có endpoint ẩn.

**EN —** Check `versionCode` with `gplaydl info com.fuct`; diff response fields with `fap extract` + `analysis/keys_schema.py`; read status mappings from the app's own functions in a disassembly kept **outside the repo** (or in gitignored paths), printing only identifier-shaped strings; diff the `MyFAP/…` endpoint set against [01](01-reverse-engineering.md) §B.

### 5.1 · Công cụ tự động `analysis/apk_drift.py` · Automated drift checker

**VI —** Bước 4 (endpoint) + "hằng số fap-cli có còn không" đã được **tự động hoá, OFFLINE, chỉ thư viện chuẩn** trong `analysis/apk_drift.py`. Nhận **APK base** (zip chứa `assets/index.android.bundle`) **hoặc raw Hermes bundle**:

```bash
python analysis/apk_drift.py <apk|bundle>                       # kiểm 1 build vs hằng/endpoint fap-cli
python analysis/apk_drift.py <old.apk|bundle> <new.apk|bundle>  # diff 2 build (case-SENSITIVE)
python analysis/apk_drift.py --write-v2-key <apk|bundle> [--env-file PATH]
```

Mỗi bản APK mới: chạy chế độ **diff** với bản đã kiểm gần nhất. Báo cáo in: version bytecode + số chuỗi; tập **v1** (`…/MyFAP/<Name>`) và **v2** (`MyFAP/<Name>` + `fap-proxy`) — so **phân biệt hoa/thường**; danh sách host; các hằng fap-cli (`SECRET`/`LOGIN_PREFIX`/`BASE` + `CLIENT_ID`/`ISSUER`/`REDIRECT_URI`) chỉ dưới dạng **CÓ/THIẾU**; marker `GetApiActive`/`sessionApiVersion`/OTA/`v1`/`v2`; và **số đếm + độ dài** literal "dạng khoá" mới (không in giá trị). Tool còn so với **endpoint fap-cli thực sự gọi** (quét `call("…"` trong `fapc/` + khoá dict `SIMPLE` của `extract.py`) ⇒ báo ngay nếu một endpoint fap-cli dùng **biến mất** khỏi build.

**Mã thoát (dùng cho cron/CI):**
- `0` — không có gì fap-cli **đang dựa vào** bị đổi.
- `1` — có thay đổi fap-cli phụ thuộc: một endpoint fap-cli gọi **thiếu** trong build, **hoặc** `SECRET` (HMAC v1) / `BASE` không còn thấy.
- `2` — lỗi đầu vào (file hỏng, version bytecode chưa hỗ trợ) hoặc `--write-v2-key` **từ chối**.

`--write-v2-key` dò **theo cấu trúc** chuỗi hằng dùng làm khoá `HmacSHA256` trong hàm checksum v2 (hàm ký `token + "MyFAP" + epoch`), **chỉ chấp nhận khi đúng MỘT ứng viên** (0 hoặc >1 ⇒ từ chối, exit 2), kiểm khoá **khác** secret v1/tiền tố login, rồi thay/append dòng `FAP_V2_KEY=…` trong file env (atomic, `chmod 0600` best-effort, giữ nguyên mọi dòng khác). Bản chưa có v2 (vd 2.0.4) ⇒ 0 ứng viên ⇒ từ chối. **Cần** `hermes-dec` hoặc `hbc-disassembler` cho riêng `--write-v2-key` (phần báo cáo drift thì không).

> 🔒 **VI —** Tool **không bao giờ in secret/PII.** Mọi chuỗi in ra qua `safe()` (che credential, hex≥12 có chữ số, email, mã SV, JWT, dãy số dài, token dài, tên riêng VN) — chỉ in chuỗi dạng **định danh**. `--write-v2-key` **không** in giá trị khoá, chỉ in `FAP_V2_KEY written (<N> chars, sha256 <8 hex đầu>)`. Khi dò bằng `hbc-disassembler`, tool ghi `.hasm` vào thư mục tạm rồi **xoá ngay** (bundle app chứa dữ liệu cá nhân của người khác). `FAP_V2_KEY` **chưa được fap-cli dùng** (v1 vẫn chạy — xem [21-api-v2](21-api-v2.md)); nó được ghi sẵn cho ngày phải chuyển v2.

**EN —** `analysis/apk_drift.py` automates endpoint + "do fap-cli's constants still exist" checks, **offline, stdlib only**, on a base **APK** (zip with `assets/index.android.bundle`) or a raw Hermes bundle. For each new APK run it in **diff** mode against the last-audited build. It prints the bytecode version + string count; the **v1** and **v2** endpoint sets (case-**sensitive** diff); hosts; fap-cli constants as **present/missing only**; the `GetApiActive`/`sessionApiVersion`/OTA/`v1`/`v2` markers; and the **count + lengths** of new key-like literals (never their values). It also compares against the endpoints fap-cli actually calls (scanning `call("…"` across `fapc/` plus the `SIMPLE` dict in `extract.py`), flagging any that **vanished** from the build. Exit codes: `0` nothing fap-cli relies on changed; `1` something did (a called endpoint missing, or `SECRET`/`BASE` gone); `2` input error or `--write-v2-key` refusal. `--write-v2-key` locates the v2 `HmacSHA256` key **structurally**, accepts it **only when exactly one candidate** exists (else refuses, exit 2), checks it differs from the v1 secret/login prefix, and writes/replaces the `FAP_V2_KEY=` line in the env file atomically (`chmod 0600` best-effort, other lines preserved); it needs `hermes-dec` or `hbc-disassembler` (the drift report does not). The tool **never prints secrets/PII** — every string is masked and `--write-v2-key` prints only `FAP_V2_KEY written (<N> chars, sha256 <first 8 hex>)`; any temporary `.hasm` is deleted immediately. `FAP_V2_KEY` is **not consumed by fap-cli yet** (v1 still works — see [21-api-v2](21-api-v2.md)); it is written ahead of a future v2 migration.

> ⚠️ **VI — Từ 2.0.5, versionCode KHÔNG còn đủ.** App tự cập nhật JS qua **OTA** (máy chủ của bên phát triển app — `codepushota.ptudev.net`, không phải `fpt.edu.vn`), có cả bản **bắt buộc reload ngay**. Endpoint, trường, ánh xạ mã có thể đổi mà Play Store **không** có bản mới. Cách theo dõi:
> 1. Định kỳ `fap extract` rồi so `analysis/keys_schema.py` với lần trước — đổi khoá = đáng xem.
> 2. Trên máy/emulator **của mình**, xem `adb logcat` dòng `[OTA]` ("Update available", "Bundle … ready"); có bundle OTA thì phân tích **bundle đó** chứ không phải asset trong APK.
> 3. **Không** tự gọi máy chủ OTA (cần deployment key, đăng ký deviceId — không phải dữ liệu của mình).
> 4. Mỗi APK mới: chạy lại bước 3–4 ở trên. Đặc tả API v2 (chưa dùng): [21-api-v2](21-api-v2.md).
>
> ⚠️ **EN — Since 2.0.5 the versionCode is no longer enough:** the app updates its JS **over the air** (the vendor's server, not `fpt.edu.vn`), including mandatory reloads, so endpoints/fields/mappings can change with no new Play release. Diff `analysis/keys_schema.py` output periodically, watch `[OTA]` lines in `adb logcat` on your own device and analyse the downloaded bundle, never query the OTA server yourself, and re-run steps 3–4 for every new APK. API v2 spec: [21-api-v2](21-api-v2.md).

---

## 6. Phiên bản đã kiểm · Versions checked

| versionCode | Tên · Name | Kết quả · Result |
|---|---|---|
| 26 | myFAP 2.0.4 | 38 endpoint (37 MyFAP + GetRequiredSurvey), không endpoint ẩn; `studentStatus` chỉ có nhánh 0/1 (mọi mã khác = "từ chối") |
| 29 | myFAP 2.0.5 | **v1 y hệt** (37 + GetRequiredSurvey; SECRET/BASE/CLIENT_ID/ISSUER/REDIRECT_URI giữ nguyên ⇒ fap-cli chạy bình thường). **Mới:** API v2 qua `fap-proxy.fpt.edu.vn` (39 đường dẫn, chọn bằng `GetApiActive`, mặc định v1 — [21](21-api-v2.md)); `studentStatus` thêm `2` Hủy / `3` Chờ thanh toán / Khác (§1); OTA tự host thay CodePush (§5); minSdk 24 → 32, targetSdk 35 → 37; bỏ ô "Thanh toán điện tử" khỏi trang chủ. `attendanceStatus` không đổi. Bundle **vẫn** chứa dữ liệu cá nhân của người khác |

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
