# Phân tích app FAP (FPT) — Quy trình reverse-engineering & Toàn bộ API

> File này gồm 2 phần: **(A) Quy trình từng bước** để bạn tự làm lại và hiểu cách hoạt động, và **(B) Sản phẩm** — bảng tra cứu toàn bộ API mà app gọi.
> Dữ liệu kèm theo: [`analysis/api-endpoints.json`](../analysis/api-endpoints.json) (dạng máy đọc được).

---

## 0. Tóm tắt

| Mục | Kết quả |
|---|---|
| Package | `com.fuct` (app FAP của FPT) |
| Định dạng tải về | **Split APK / App Bundle** (1 base + các config: abi, ngôn ngữ, mật độ màn hình) |
| Công nghệ | **React Native + Hermes** (thấy `libhermes.so`, `libreactnative.so`, `libreanimated.so`) |
| Logic thật nằm ở | `assets/index.android.bundle` — **Hermes bytecode v96** (6.48 MB) |
| Số endpoint tìm thấy | **43** (37 ở `api.fpt.edu.vn`, còn lại survey/invoice/web) |
| Kiểu gọi | **Toàn bộ là HTTP GET**, tham số nối vào query string, gọi qua `fetch()` |
| Cơ chế bảo vệ | `Authen` & `checksum` là **chữ ký MD5** tính ở client (`Md5.hashStr`) |

---

## A. QUY TRÌNH TỪNG BƯỚC (để học)

Máy bạn chỉ cần **Python 3** (đã có 3.13). Không cần Java cho hướng này.

### Bước 1 — Hiểu mình đang cầm gì
Bộ file tải về là **split APK**. File logic chính nằm trong `com.fuct-26.apk` (và bản sao trong `...-asset.apk`). Các file `config.*` chỉ là tài nguyên (thư viện native theo CPU, ngôn ngữ, ảnh theo DPI).

### Bước 2 — Soi ruột APK (APK = file ZIP)
```bash
python -c "import zipfile;z=zipfile.ZipFile('com.fuct-26.apk');print('\n'.join(n for n in z.namelist() if n.endswith('.dex') or n.endswith('.so') or 'bundle' in n))"
```
Thấy `classes*.dex` (vỏ Java của React Native — ít giá trị) và `assets/index.android.bundle` (← **mục tiêu**).

### Bước 3 — Xác định loại bundle (Hermes hay JS thường)
```bash
python -c "d=open('extracted/index.android.bundle','rb').read(); print(d[:8].hex())"
```
Nếu bắt đầu bằng `c61fbc03c103191f` → **Hermes bytecode** (nhị phân, không đọc trực tiếp được). Byte thứ 8–11 là số phiên bản (ở đây = **96**).

### Bước 4 — Rút bundle ra đĩa
```bash
python -c "import zipfile;open('extracted/index.android.bundle','wb').write(zipfile.ZipFile('com.fuct-26.apk').read('assets/index.android.bundle'))"
```

### Bước 5 — Cài tool decompile Hermes (thuần Python)
```bash
py -m pip install hermes-dec
```
Tool nằm ở `...\Python313\Scripts\` (chưa có trong PATH → gọi bằng đường dẫn đầy đủ).

### Bước 6 — Disassemble bytecode ra dạng đọc được
```bash
"<Scripts>/hbc-disassembler" extracted/index.android.bundle extracted/disasm.hasm
```
Ra file `.hasm` ~72 MB. Mỗi lệnh kèm chú thích `# String: '...'` chứa **chuỗi gốc đã tách đúng** (đây là chìa khóa).

> Lưu ý: `hbc-decompiler` (ra JS giả) hiện **lỗi trên Python 3.13** (`Callable._abc_registry`). Không sao — bản disassembly đủ để lấy API. Muốn chạy decompiler thì dùng Python 3.10/3.11.

### Bước 7 — Trích URL & endpoint
Quét các chuỗi `# String: '...'` trong `.hasm`, lọc ra cái chứa `fpt.edu.vn` / bắt đầu bằng `http`. (Đừng quét thô trên file `.bundle` nhị phân — Hermes xếp các chuỗi dính nhau nên sẽ ra rác.)

### Bước 8 — Ghép method + tham số cho từng endpoint
Tách `.hasm` theo từng `=> [Function #N ...]`. Với mỗi hàm có chứa URL, gom các chuỗi tham số (`&xxx=`) và literal method trong cùng hàm đó → suy ra method + danh sách tham số. Kết quả nằm ở phần B.

---

## B. SẢN PHẨM — TOÀN BỘ API

**Base API:** `https://api.fpt.edu.vn/fap/api/MyFAP/`
**Cách dùng chung:** mọi request là `GET`, tham số nằm trong query string. Hầu hết cần `campusCode`, `rollNumber` (MSSV), `Authen` và `checksum` (chữ ký MD5).

### Xác thực / Đăng nhập

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/AuthenticationByFeId` | GET | `campusCode`, `checksum` |
| `…/MyFAP/AuthenticationByGoogleAccessToken` | GET | `campusCode`, `checksum`, `token` |
| `…/MyFAP/AuthenticationByUsername` | GET | `CampusCode`, `Authen`, `Password`, `userName` |
| `…/MyFAP/GetTokenWithEmp` | GET | `campusCode`, `Authen`, `roll` |

### Hệ thống / Campus

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/GetAllActiveCampus` | GET | — |
| `…/MyFAP/GetCampusInfo` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetSemester` | GET | `campusCode`, `Authen`, `checksum` |
| `…/MyFAP/GetSemesterMark` | GET | `CampusCode`, `Authen`, `rollNumber` |
| `…/MyFAP/GetVersion` | GET | — |
| `…/MyFAP/GetWeekByDate` | GET | `date` |

### Hồ sơ sinh viên

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/CheckUpdateProfile` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetStudentById` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/RetriveImage` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |

### Học tập / Điểm

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/AcademicTranscript` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetCourseOfSemester` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber`, `semester` |
| `…/MyFAP/GetMarkByCourse` | GET | `campusCode`, `Authen`, `CourseId`, `checksum`, `rollNumber` |
| `…/MyFAP/GetScheduleExam` | GET | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` |
| `…/MyFAP/GetStudentAttendances` | GET | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` |
| `…/MyFAP/GetStudentMark` | GET | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` |
| `…/MyFAP/GetSubjectBySemester` | GET | `campusCode`, `Authen`, `Semester`, `checksum` |
| `…/MyFAP/GetSubjets` | GET | `campusCode`, `Authen`, `checksum` |
| `…/MyFAP/getCourseAttendance` | GET | `campusCode`, `Authen`, `ClassName`, `Semester`, `SubjectCode`, `checksum`, `rollNumber` |

### Hoạt động / Phong trào / Đánh giá

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/AddRate` | GET | `campusCode`, `Authen`, `checksum`, `rateComment`, `rateValue`, `rateid` |
| `…/MyFAP/CheckOpenFeedBack` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetActivityStudent` | GET | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber` |
| `…/MyFAP/GetActivityStudentByWeek` | GET | `campusCode`, `Authen`, `Semester`, `checksum`, `rollNumber`, `week`, `year` |
| `…/MyFAP/GetDiemphongtrao` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber`, `semester` |
| `…/MyFAP/GetStudentRate` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |

### Tài chính

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/GeFeeByRoll` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetBalance` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `https://dng.fpt.edu.vn/Invoice` | GET | `StudentId` |

### Tin tức / Thông báo

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/GetNotificationByDonor` | GET | `CampusCode`, `Authen`, `rollNumber` |
| `…/MyFAP/GetNotificationByRoll` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |
| `…/MyFAP/GetTop10News` | GET | `campusCode`, `Authen`, `checksum`, `type` |
| `…/MyFAP/SearchNews` | GET | `campusCode`, `Authen`, `checksum`, `keysearch`, `type` |

### Đơn từ

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/GetApplication` | GET | `campusCode`, `Authen`, `checksum`, `rollNumber` |

### Thiết bị / Push token

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `…/MyFAP/UpdateTokedevices` | GET | `CampusCode`, `Email`, `checksum`, `tokendevice` |
| `…/MyFAP/UpdateTokenDonor` | GET | `CampusCode`, `rollNumber`, `tokendevice` |

### Khảo sát

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `https://survey.fpt.edu.vn` | GET | `checksum` |
| `https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey` | GET | `username`, `checksum` |

### Khác

| Endpoint | Method | Tham số (query) |
|---|---|---|
| `https://fap.fpt.edu.vn` | GET | — |
| `https://fap.fpt.edu.vn/temp/` | GET | — |
| `https://googleauthensite01.fpt.edu.vn:97` | GET | — |


### Cách app dựng một request (ví dụ đã giải mã)
Hàm đăng nhập (`AuthenticationByUsername`) thực chất chạy đại ý:
```js
const authen = Md5.hashStr(/* tính từ username + password (+ secret) */);
fetch("https://api.fpt.edu.vn/fap/api/MyFAP/AuthenticationByUsername?CampusCode=" +
      campus + "&userName=" + user + "&Password=" + pass + "&Authen=" + authen)
   .then(r => r.json())
   .catch(e => console.error("Error is: ", e));
```
- Không có options `{method:...}` ⇒ `fetch` mặc định **GET**.
- `Authen` / `checksum` được sinh bằng **MD5 ở client** để server kiểm tra tính toàn vẹn của request.

---

## C. Nhận xét bảo mật (điểm để học)

Đây là những quan sát về **thiết kế** (không phải hướng dẫn tấn công):
1. **GET + tham số nhạy cảm trong URL:** cả `Password` và token được đẩy vào query string → dễ lọt vào log server, lịch sử proxy, cache. Thực hành tốt: dùng `POST` + body + HTTPS, không bao giờ để mật khẩu trên URL.
2. **Ký bằng MD5 ở client:** MD5 đã lỗi thời; chữ ký tính ở client luôn có thể bị dịch ngược. Đây là "security by obscurity", không thay được xác thực phía server.
3. **Endpoint dễ đoán & gom 1 controller (`MyFAP`):** tốt cho việc đọc hiểu, nhưng nhắc rằng quyền truy cập phải được kiểm ở server theo từng tài khoản, không dựa vào việc client giấu URL.

---

## D. Sử dụng có trách nhiệm

- Việc bạn **dịch ngược app của chính trường để học/làm tài liệu** là mục đích chính đáng và file này phục vụ điều đó.
- **Không** nên: dùng chữ ký dựng lại để gọi thẳng server thật một cách tự động, thu thập (scrape) dữ liệu hàng loạt, hay truy cập dữ liệu của sinh viên khác — những việc này có thể vi phạm quy định của trường và pháp luật, kể cả khi kỹ thuật làm được.
- Nếu muốn thử gọi API: chỉ dùng **tài khoản của chính bạn**, ở mức tối thiểu, và dừng nếu nhà trường không cho phép.

---

## Phụ lục — file sinh ra
| File | Nội dung |
|---|---|
| `analysis/index.android.bundle` | Bundle Hermes gốc rút từ APK |
| `analysis/disasm.hasm` | Bản disassembly (72 MB) |
| `analysis/strings_clean.txt` | 22.651 chuỗi sạch tách từ bảng chuỗi Hermes |
| `analysis/api-endpoints.json` | **43 endpoint** kèm method + tham số (máy đọc được) |
