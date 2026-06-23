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
