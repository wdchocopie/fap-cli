# Bản đồ checksum theo từng endpoint · Per-endpoint checksum map

**VI —** Mỗi endpoint FAP ký `checksum` bằng tham số khác nhau (reverse từ bytecode Hermes). Có 3 dạng:
**EN —** Each FAP endpoint signs `checksum` with different inputs (reversed from Hermes bytecode). Three kinds:

| Hàm · Function | Công thức · Formula |
|---|---|
| `getCheckSumAuthenicated(a, b)` (cs12) | `base64(HMAC_SHA1(SECRET, a + "MYFAP" + b + "DD/MM/YYYY HH:00"))` → `=`→`%3d`, ` `→`+` |
| `getCheckSumLogin(campus)` (cs14) | `base64(HMAC_SHA1(SECRET, LOGIN_PREFIX + campus + "DD/MM/YYYY HH:00"))` → encode |
| *(không checksum · none)* | endpoint không gửi `&checksum=` |

> `SECRET`, `LOGIN_PREFIX` trích từ APK công khai · extracted from the public APK. Giờ tính theo **giờ VN (UTC+7)**, ổn định trong 1 giờ · VN time, stable for 1 hour.

## Endpoint → checksum

| Endpoint | checksum dùng · uses |
|---|---|
| `GetStudentById`, `GetStudentMark`, `GetStudentAttendances`, `GetScheduleExam`, `GetActivityStudent`, `AcademicTranscript`, `GetCampusInfo`, `CheckUpdateProfile`, `GetBalance`, `GeFeeByRoll`, `GetStudentRate`, `CheckOpenFeedBack`, `GetApplication`, `GetNotificationByRoll`, `GetDiemphongtrao`, `GetCourseOfSemester`, `getCourseAttendance` | `cs12(rollNumber, campusCode)` |
| `GetSubjectBySemester` | `cs12(Semester, campusCode)` |
| `GetTop10News` | `cs12(type, campusCode)` |
| `SearchNews` | `cs12(keysearch, campusCode)` *(suy luận · inferred)* |
| `GetSemester`, `GetSubjets` | `cs14(campusCode)` |
| `GetSemesterMark` | *(không checksum · none)* |
| `AuthenticationByFeId` (login) | `cs14(campusCode)`, gửi access token trong body `{token}` |
| `AuthenticationByUsername` (login) | `Password=MD5(password)`, `Authen=4e9800998ecf8427e` (hằng số · constant) |
| Khảo sát · Survey (`survey.fpt.edu.vn`) | `cs12` với `SECRET_SURVEY` riêng · separate secret |

## Cách dùng trong code · Using it (`fapc/core/api.py`)
```python
from fapc.core.api import call, checksum_auth, checksum_login
# mặc định · default = cs12(roll, campus):
call("GetStudentMark", [("campusCode",c),("Authen",t),("Semester",s),("rollNumber",r)], r, c)
# override:
call("GetSemester", [("campusCode",c),("Authen",t)], r, c, checksum_value=checksum_login(c))
call("GetSubjectBySemester", [...], r, c, checksum_value=checksum_auth(s, c))
call("GetSemesterMark", [...], r, c, checksum_value=False)   # không gửi checksum
```
