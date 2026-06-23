# Danh mục toàn bộ thông tin có thể extract từ FAP

Tài liệu này tổng hợp **khoảng 35 endpoint API** của ứng dụng MyFAP (FPT University, package `com.fuct`, React Native + Hermes bytecode) cùng với **dữ liệu cục bộ** lưu trên thiết bị. Hầu hết endpoint dùng base URL `https://api.fpt.edu.vn` (riêng khảo sát dùng `survey.fpt.edu.vn`, hóa đơn Đà Nẵng dùng `dng.fpt.edu.vn`). Cơ chế xác thực gồm hai phần: tham số **`Authen`** (token đăng nhập lưu plaintext trong AsyncStorage key `authenkey`) và **`checksum`** ký theo **HMAC-SHA1** với SECRET hard-code trong hàm `getCheckSumAuthenicated`, công thức dựng từ `rollNumber + "MYFAP" + campusCode + giờ hiện tại` (sai checksum trả `code=201` "Thông tin checksum không chính xác"). Ngoài API, một lượng lớn dữ liệu (hồ sơ đầy đủ, danh mục môn ~3240 lớp, danh sách học kỳ, số dư) đã được **cache offline** trong SQLite `catalystLocalStorage`, đọc được không cần mạng. Mức độ tin cậy: `confirmed` = có mẫu phản hồi thật / cache thật; `high` = đọc trường trực tiếp trong bundle; `medium`/`low` = suy đoán từ tên endpoint và nhãn UI.

---

## A. Qua API (online)

### A.1. Xác thực (Authentication)

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `AuthenticationByUsername` | Đăng nhập bằng username + password, trả token phiên | `CampusCode`, `Authen`, `Password`, `userName` | `token`, `rollNumber`, `email`, `fullname`, `typeAcc`, `campus` | high |
| `AuthenticationByFeId` | Đăng nhập bằng FE Id (định danh nội bộ FPT) | `campusCode`, `checksum` | `token`, `rollNumber`, `email`, `fullname` | high |
| `AuthenticationByGoogleAccessToken` | Đổi access token Google (email @fpt.edu.vn) lấy token FAP | `campusCode`, `checksum`, `token` (Google access token) | `token`, `rollNumber`, `email`, `fullname`, `typeAcc` | high |
| `GetTokenWithEmp` | Cấp token cho tài khoản nhân viên/giảng viên theo mã roll | `campusCode`, `Authen`, `roll` | `token`, `fullname`, `email`, `typeAcc` | medium |

> Lưu ý: `AuthenticationByUsername` đẩy mật khẩu trong **query string (GET)** — dễ lọt log. Tham số `Authen` ở các luồng login là chuỗi checksum/chữ ký, không phải mật khẩu thô. Token sau đăng nhập lưu **plaintext** ở `RKStorage:authenkey`.

### A.2. Hồ sơ (Profile)

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetStudentById` | Hồ sơ chi tiết sinh viên (cá nhân, ngành, học vụ, liên hệ phụ huynh) | `campusCode`, `rollNumber`, `Authen`, `checksum` | `rollNumber`, `fullname`, `firstName`, `lastName`, `middleName`, `dateOfBirth`, `gender`, `email`, `mobilePhone`, `address`, `major`, `nganh`, `chuyenNganh`, `batch`, `lopchinh`, `currentTermNo`, `statusCode`, `memberCode`, `iDCard`, `parentName`, `parentPhone`, `parentEmail`, `parentAddress` | high |
| `RetriveImage` *(sai chính tả "Retrive")* | Ảnh thẻ/avatar sinh viên (base64 hoặc URL) | `campusCode`, `rollNumber`, `Authen`, `checksum` | `image` / `imageBase64` / `url` (data vô hướng) | high |
| `CheckUpdateProfile` | Cờ kiểm tra sinh viên có phải cập nhật hồ sơ tại fap.fpt.edu.vn không | `campusCode`, `rollNumber`, `Authen`, `checksum` | `hasUpdateProfile` / `isUpdate`, `message` | high |
| `GetCampusInfo` | Thông tin/liên hệ một campus | `campusCode`, `Authen`, `checksum`, `rollNumber` | `campusName`, `campusCode`, `address`, `phone`, `email` | medium |

### A.3. Học tập & Điểm

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `AcademicTranscript` | Bảng điểm tổng toàn khóa (mọi môn, đạt/không đạt) | `campusCode`, `Authen`, `checksum`, `rollNumber` | `subjectCode`, `subjectName`, `semesterName`, `averageMark`, `gradeStatus`, `credit`, `result`, `attempt` | high |
| `GetStudentMark` | Điểm **tổng kết** mỗi môn trong một kỳ (1 dòng/môn) + `courseID` để tra chi tiết. *(KHÔNG trả điểm thành phần — đối chiếu mẫu thật `output/api/GetStudentMark.json`; muốn thành phần phải gọi `GetMarkByCourse`.)* | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` | `subjectCode`, `className`, `averageMark`, `status`, `courseID` | high |
| `GetMarkByCourse` | Chi tiết điểm của một môn theo `CourseId` | `campusCode`, `Authen`, `CourseId`, `checksum`, `rollNumber` *(có thể cần `SubjectCode`)* | `subjectCode`, `subjectName`, `component`, `weight`, `value`, `averageMark`, `gradeStatus` | high |
| `GetSemesterMark` | Điểm tổng kết / GPA theo từng kỳ | `CampusCode` *(C hoa)*, `Authen`, `rollNumber` *(không có checksum)* | `semesterName`, `averageMark`, `gpa`, `termID`, `result` | medium |
| `GetSubjectBySemester` | Danh mục môn mở trong một kỳ | `campusCode`, `Authen`, `Semester`, `checksum` | `subjectCode`, `subjectName`, `className`, `startDate`, `endDate` | high |
| `GetSubjets` *(sai chính tả "Subjets")* | Toàn bộ danh mục môn của campus (để cache tra tên) | `campusCode`, `Authen`, `checksum` | `subjectCode`, `subjectName`, `className`, `startDate`, `endDate` | medium |

### A.4. Thời khóa biểu & Điểm danh

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetCourseOfSemester` | Danh sách môn/lớp đăng ký trong kỳ (kèm CourseId) | `campusCode`, `Authen`, `checksum`, `rollNumber`, `semester` | `courseId`, `subjectCode`, `subjectName`, `groupName`, `slot`, `room`, `lecturer`, `sessionNo` | high |
| `GetActivityStudent` | Lịch học theo kỳ (xem theo ngày, đếm buổi/ngày) | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` | `date`, `slot`, `subjectCode`, `room`, `lecturer`, `sessionNo`, `groupName`, `status` | high |
| `GetActivityStudentByWeek` | Thời khóa biểu theo tuần | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber`, `week`, `year` | `date`, `slot`, `subjectCode`, `room`, `lecturer`, `sessionNo`, `groupName`, `dayOfWeek` | high |
| `GetScheduleExam` | Lịch thi trong một kỳ | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` | `examSubject`, `examDate`, `examTime`, `examRoom`, `examType`, `examForm` | high |
| `GetStudentAttendances` | Tổng hợp điểm danh theo kỳ (số buổi, % chuyên cần) | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` | `groupName`, `subjectCode`, `rollNumber`, `numberOfTakenAttendances`, `numberOfAttendances`, `attendance`, `startDate`, `endDate` | **confirmed** |
| `getCourseAttendance` | Chi tiết điểm danh từng buổi của một lớp/môn | `campusCode`, `Authen`, `ClassName`, `Semester`, `SubjectCode`, `checksum`, `rollNumber` | `date`, `slot`, `className`, `lecturer`, `attendanceStatus`, `present`, `absent` | high |

> `GetStudentAttendances` là endpoint **duy nhất có mẫu phản hồi thật** (HTTP 200, envelope `{message, code, errorMessage, data}`, `data` là list 8 trường). Trường `attendance` là phần trăm chuyên cần (vd `100`).

### A.5. Hoạt động / Phong trào

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetDiemphongtrao` | Điểm phong trào / rèn luyện theo kỳ | `campusCode`, `rollNumber`, `semester`, `Authen`, `checksum` | `semester`, `activityName`, `point`, `totalPoint`, `PhongTrao`, `joinMovement` | high |
| `GetActivityStudent` *(nhánh hoạt động)* | Hoạt động ngoại khóa đã/đang tham gia trong kỳ | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` | `eventName`, `activityDate`, `point`, `status` | low |
| `GetStudentRate` | Các mục đánh giá/feedback giảng viên-môn của sinh viên | `campusCode`, `rollNumber`, `Authen`, `checksum` | `rateId`, `rateValue`, `rateComment`, `hasStudentRated`, `subjectCode`, `subjectName`, `lecturer` | high |
| `CheckOpenFeedBack` | Cờ kiểm tra có đợt feedback/khảo sát đang mở không | `campusCode`, `rollNumber`, `Authen`, `checksum` | `isOpen`, `hasFeedback`, `message` | high |

### A.6. Tài chính

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetBalance` | Số dư tài khoản hiện tại (VND) | `campusCode`, `Authen`, `checksum`, `rollNumber` | `balance` (data vô hướng, số) | high |
| `GeFeeByRoll` *(sai chính tả "GeFee")* | Danh sách khoản học phí/hóa đơn theo MSSV | `campusCode`, `Authen`, `checksum`, `rollNumber` | `amount`, `invoiceNo`, `invoiceDate`, `note`, `rollNumber`, `balance` | high |
| `Invoice` *(dng.fpt.edu.vn)* | Trang HTML hóa đơn học phí (chỉ campus Đà Nẵng), mở WebView | `StudentId` (= rollNumber) | *(HTML, không phải JSON)* | confirmed |

### A.7. Tin tức / Thông báo

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetTop10News` | 10 tin tức mới nhất của campus theo loại | `campusCode`, `Authen`, `checksum`, `type` | `Title`, `Contents`, `EntryDate`, `EntryBy` *(có thể `Url`/`Image`)* | medium |
| `SearchNews` | Tìm tin tức theo từ khóa + loại | `campusCode`, `Authen`, `checksum`, `keysearch`, `type` | `Title`, `Contents`, `EntryDate`, `EntryBy` | medium |
| `GetNotificationByRoll` | Thông báo cá nhân gửi tới sinh viên | `campusCode`, `Authen`, `checksum`, `rollNumber` | `Title`, `Contents`, `EntryBy`, `EntryDate` | high |
| `GetNotificationByDonor` | Thông báo cho phụ huynh/người bảo trợ | `CampusCode` *(C hoa)*, `Authen`, `rollNumber` *(không có checksum)* | `Title`, `Contents`, `EntryBy`, `EntryDate` | high |
| `GetApplication` | Danh sách đơn từ + trạng thái xử lý | `campusCode`, `Authen`, `checksum`, `rollNumber` | `w_app_id`, `name`, `description`, `processNote`, `createDate`, `studentStatus` | high |

> `keysearch` được `encodeURIComponent` + trim trước khi gọi. News và Notification dùng chung hạ tầng (state `dataNotifi`), tên trường gốc từ FAP là `Title`, `Contents` (có "s"), `EntryDate`, `EntryBy`.

### A.8. Hệ thống

| Endpoint | Lấy gì | Tham số | Trường trả về | Độ tin |
|---|---|---|---|---|
| `GetAllActiveCampus` | Danh sách campus đang hoạt động (cho dropdown login) | *(không cần)* | `campusCode`, `campusName` | high |
| `GetSemester` | Danh sách học kỳ của campus | `campusCode`, `Authen`, `checksum` | `semesterName`, `termID`, `campusID`, `startDate`, `endDate` | high |
| `GetWeekByDate` | Quy đổi một ngày sang tuần học | `date` (YYYY-MM-DD) | `week`, `year`, `startDate`, `endDate` | medium |
| `GetVersion` | Phiên bản app mới nhất + cờ bắt buộc cập nhật + bảo trì | *(không cần, kèm hằng checksum cố định)* | `version`, `forceUpdate`, `url` | medium |
| `GetRequiredSurvey` *(survey.fpt.edu.vn)* | Khảo sát bắt buộc cần hoàn thành | `username`, `checksum` *(SECRET riêng)* | `surveyId`, `surveyName`, `url`, `deadline`, `isRequired` | medium |
| `UpdateTokedevices` *(GHI, sai chính tả "Tokedevices")* | Đăng ký/cập nhật FCM token cho sinh viên | `CampusCode`, `Email`, `checksum`, `tokendevice` | `code`, `message` | high |
| `UpdateTokenDonor` *(GHI)* | Đăng ký FCM token cho phụ huynh | `CampusCode`, `rollNumber`, `tokendevice` *(không có checksum)* | `code`, `message` | high |
| `AddRate` *(GHI, axios POST)* | Gửi đánh giá/feedback (điểm + bình luận) | `campusCode`, `Authen`, `rateid`, `rateValue`, `rateComment`, `checksum` | `code`, `message` | high |

---

## B. Dữ liệu cục bộ (offline)

### B.1. RKStorage (SQLite `catalystLocalStorage`)

| Key | Lấy gì | Trường / Giá trị | Nhạy cảm | Độ tin |
|---|---|---|---|---|
| `authenkey` | Token đăng nhập FAP (= tham số `Authen`) | chuỗi ~50 ký tự | **CAO** — khóa truy cập mọi API | confirmed |
| `profile` | Hồ sơ sinh viên đầy đủ (bản local của `GetStudentById`) | **57 trường (đã xác nhận thực tế)**: `rollNumber`, `oldRollNumber`, `lastName/middleName/firstName`, `fullname`, `dateOfBirth`, `gender`, `iDCard`, `dateOfIssue`, `placeOfIssue`, `address`, `homePhone`, `mobilePhone`, `email`, `parentName/Job/Phone/Address/Email`, `placeOfWork`, `memberCode`, `capstoneProject`, `tenDetaiTN`, `major`, `nganh`, `chuyenNganh`, `batch`, `lopchinh`, `currentTermNo`, `statusCode`(=HD), `enrolDate`, `progress`, `termPaid`, `loaiTaiChinh`, các quyết định học vụ `qD_*` (`qD_ChuyenNganh`, `qD_ThoiHoc`, `qD_BaoLuu_Exchange`, `qD_TN`...) | **CAO** — CMND/CCCD, ngày sinh, SĐT, phụ huynh | confirmed |
| `semester` | Danh sách 28 học kỳ (bản local của `GetSemester`) | `campusID`, `endDate`, `semesterName`, `startDate`, `termID` | Thấp | confirmed |
| `subjects` | Danh mục môn lớn nhất ~504KB (3240 lớp) | `className`, `endDate`, `startDate`, `subjectCode`, `subjectName` | Thấp | confirmed |
| `fcmToken` | FCM token thiết bị (= `tokendevice`) | chuỗi 142 ký tự | Trung bình — định danh thiết bị | confirmed |
| `balance` | Số dư tài khoản (bản local của `GetBalance`) | chuỗi số ~5 ký tự | Thấp | confirmed |
| `email` / `fullname` / `rollnumber` / `campus` / `typeAcc` | Định danh tài khoản tách lẻ | `email`(26B), `fullname`(15B), `rollnumber`(8B), `campus`='FPTU'(4B), `typeAcc`='student'(7B) | Trung bình | confirmed |

> `rollnumber` + `campus` là nguyên liệu bắt buộc để dựng checksum. Học kỳ hiện tại trong dữ liệu mẫu là `Summer2026`.

### B.2. Nguồn từ APK

| Tài sản | Lấy gì | Nội dung chính | Độ tin |
|---|---|---|---|
| `assets/index.android.bundle` | Toàn bộ logic JS (Hermes bytecode v96, ~6.48MB) | Mọi URL endpoint, `getCheckSumAuthenicated` (SECRET HMAC-SHA1 ~130 ký tự hard-code), nhãn màn `lb_*` | confirmed |
| `AndroidManifest` | Khai báo app | package `com.fuct`, quyền `INTERNET` + FCM/push, `MainActivity` (ReactActivity), `CodePushDeploymentKey` | medium |
| `appcenter-config.json` | Cấu hình Microsoft AppCenter | `app_secret`, endpoint `appcenter.ms`, `deployment_key` (CodePush OTA) | medium |

---

## C. Ghi chú khai thác

**Hữu ích nhất để build sản phẩm:**
- **Thời khóa biểu:** `GetActivityStudentByWeek` (TKB theo tuần) + `GetWeekByDate` (quy đổi ngày → tuần) + `GetCourseOfSemester` (lấy `CourseId`/danh sách lớp). Đây là bộ ba lõi cho app lịch học.
- **Điểm:** `GetStudentMark` (điểm **tổng kết** mỗi môn trong kỳ, kèm `courseID`) + `AcademicTranscript` (bảng điểm toàn khóa) + `GetMarkByCourse` (**điểm thành phần** một môn theo `courseID`). `GetSemester` cung cấp danh sách kỳ để đổ dropdown.
- **Điểm danh:** `GetStudentAttendances` (đã có mẫu thật, đáng tin nhất) + `getCourseAttendance` (chi tiết từng buổi).
- **Học phí:** `GeFeeByRoll` (danh sách hóa đơn) + `GetBalance` (số dư).
- **Tra cứu nhanh / offline:** cache `RKStorage:profile`, `:subjects`, `:semester` cho phép dựng phần lớn UI mà **không cần gọi mạng hay checksum**.

**Endpoint GHI / ĐỔI dữ liệu — CẢNH BÁO (gọi sẽ thay đổi trạng thái máy chủ, không phải chỉ đọc):**
- `AddRate` — **ghi đánh giá** (dùng axios POST, tham số trên query string). Gửi là **không hoàn tác**; chỉ gọi khi thực sự muốn nộp feedback, với `rateid` hợp lệ lấy từ `GetStudentRate`.
- `UpdateTokedevices` / `UpdateTokenDonor` — **đăng ký/ghi đè FCM token** đẩy. Gọi sai có thể chiếm/đổi kênh push của tài khoản. Chỉ dùng khi đăng ký thiết bị của chính mình.

**Endpoint có thể trả về rỗng giữa kỳ (bình thường, không phải lỗi):**
- `GetScheduleExam` — đầu/giữa kỳ chưa xếp lịch thi → `data=[]` (nhãn `lb_schex_notSchedule`).
- `GetStudentAttendances` / `GetStudentMark` — môn chưa bắt đầu → số buổi `0` hoặc cột điểm `null`.
- `GetDiemphongtrao` / `GetActivityStudent` — chưa tham gia hoạt động → mảng rỗng (`code` khác 200 trả `[]`).
- `GetActivityStudentByWeek` — tuần nghỉ lễ/giữa kỳ → `data` rỗng.
- `CheckOpenFeedBack` — ngoài đợt khảo sát → chuỗi rỗng `''` / `isOpen=false`.
- `GetCourseOfSemester` — khi gọi thật bằng URL trong dump trả **HTTP 404** (có thể phân biệt hoa/thường hoặc đã đổi path) — cần đối chiếu lại trước khi phụ thuộc.

---

## D. Lưu ý đạo đức / an toàn

- **Chỉ truy cập tài khoản của chính bạn.** Mọi endpoint cá nhân yêu cầu `Authen` (token của bạn) + `rollNumber` của bạn. **Tuyệt đối không lặp/quét MSSV người khác** để lấy hồ sơ, điểm, học phí — đó là truy cập trái phép dữ liệu cá nhân của người khác.
- **Gọi nhẹ nhàng, tôn trọng hệ thống.** Không quét hàng loạt, không vòng lặp tốc độ cao; thêm độ trễ hợp lý và cache lại (dùng `RKStorage:subjects`/`:semester` thay vì gọi đi gọi lại). Tránh gây tải bất thường lên cổng FAP.
- **Bảo vệ dữ liệu nhạy cảm.** `authenkey` và `profile` (CMND/CCCD, ngày sinh, SĐT, thông tin phụ huynh) lưu **plaintext** — không log ra console, không chia sẻ, không commit vào repo, không gửi sang dịch vụ bên thứ ba. Token hết hạn thì đăng nhập lại trong app chính thức.
- **Không phá vỡ/né tránh kiểm soát.** SECRET checksum và `app_secret` AppCenter trích từ bundle chỉ phục vụ tìm hiểu cá nhân; không dùng để giả mạo request, vượt xác thực, hay phân phối lại.
- **Ưu tiên endpoint chỉ-đọc.** Khi thử nghiệm, tránh `AddRate`, `UpdateTokedevices`, `UpdateTokenDonor` trừ khi chủ đích thực hiện thao tác ghi của riêng mình; thao tác ghi có thể ảnh hưởng dữ liệu thật và không hoàn tác.
