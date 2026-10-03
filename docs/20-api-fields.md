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
| `GetApplication.studentStatus` | `"0"` đang xử lý · `"1"` đã được chấp nhận · còn lại bị từ chối — theo `getStatusConfig` + bảng i18n `lb_appli_status_*` của app | Huy hiệu ⏳/✅/❌. **Cố ý khác app:** mã lạ hiện `❔ <mã>` thay vì "từ chối" |
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

---

## 6. Phiên bản đã kiểm · Versions checked

| versionCode | Tên · Name | Kết quả · Result |
|---|---|---|
| 26 | myFAP 2.0.4 | 38 endpoint (37 MyFAP + GetRequiredSurvey), không endpoint ẩn; ánh xạ mã trạng thái như §1 |

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only. Read [../SECURITY.md](../SECURITY.md).
