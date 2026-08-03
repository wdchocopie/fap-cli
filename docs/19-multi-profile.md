# Nhiều tài khoản trên 1 máy · Multi-profile

**VI —** Chạy **nhiều tài khoản FAP** trên **cùng một máy / cùng một checkout** mà token, baseline thông báo và cache **không đè nhau**. Bật bằng đúng một biến: `FAP_PROFILE`.
**EN —** Run **several FAP accounts** from **one machine / one checkout** without their tokens, alert baselines or caches overwriting each other. It is switched on by a single variable: `FAP_PROFILE`.

> ✅ **VI —** **Không đặt `FAP_PROFILE` ⇒ không có gì thay đổi.** Mọi đường dẫn resolve ra **đúng chuỗi như cũ** (`output/token.json`, `output/grade_state.json`…). Máy đang chạy **không cần migrate, không cần login lại**.
> ✅ **EN —** **With `FAP_PROFILE` unset, nothing changes.** Every path resolves to the **exact same string as before** (`output/token.json`, `output/grade_state.json`…). An existing box needs **no migration and no re-login**.

> 🔴 **VI — ĐỒNG Ý TRƯỚC, KỸ THUẬT SAU.** Mỗi người **tự chạy `fap login` của chính họ**. Bạn **KHÔNG** nhận mật khẩu, **KHÔNG** login hộ, **KHÔNG** copy token của người khác về. Sau khi họ login trên máy bạn, `refresh_token` của họ (scope `openid email profile offline_access`) **nằm trên server của bạn** cho tới khi họ thu hồi — họ phải biết và đồng ý rõ ràng điều đó.
> 🔴 **EN — CONSENT FIRST, PLUMBING SECOND.** Each person **runs their own `fap login`**. You do **not** take their password, do **not** log in on their behalf, and do **not** copy someone else's token onto your box. Once they log in on your machine their `refresh_token` (scope `openid email profile offline_access`) **lives on your server** until they revoke it — they must know that and agree to it explicitly.

---

## 1. `FAP_PROFILE` làm gì · What `FAP_PROFILE` does

| | Không đặt · Unset *(mặc định)* | `FAP_PROFILE=alice` |
|---|---|---|
| Trạng thái · State | `output/…` | `output/profiles/alice/…` |
| Cấu hình · Config | `.env` | `.env.alice` **trước**, rồi `.env` (bỏ khóa danh tính) · `.env.alice` **first**, then `.env` minus the identity keys |
| Nhãn in ra log · Log label | *(trống · none)* | ` [alice]` |
| Tiến trình · Processes | 1 bộ · one set | **1 bộ riêng cho mỗi profile** · one set **per profile** |

**VI —** Tên profile chỉ được chứa **chữ / số / `.` `_` `-`** (`fapc/core/paths.py`). Tên sai định dạng **bị bỏ qua** kèm cảnh báo ra `stderr` và tiến trình chạy **như không có profile** — tức là dùng `.env` và `output/` của **chủ máy**. Đọc kỹ cảnh báo đó, đừng lướt qua.
**EN —** A profile name may only contain **letters / digits / `.` `_` `-`** (`fapc/core/paths.py`). A malformed name is **ignored** with a `stderr` warning and the process runs **as if there were no profile** — i.e. on the **owner's** `.env` and `output/`. Read that warning; don't skim past it.

**VI —** Profile được **chốt lúc import** (các hằng đường dẫn là hằng cấp module). Đổi `FAP_PROFILE` giữa chừng trong 1 tiến trình **không có tác dụng** — đúng thiết kế: **mỗi profile một tiến trình**.
**EN —** The profile is **frozen at import time** (path constants are module-level). Changing `FAP_PROFILE` mid-process has **no effect** — by design: **one process per profile**.

### Đặt biến ở đâu · Where to set it

```bash
# 1) Trong systemd unit (KHUYẾN NGHỊ cho server) · in the systemd unit (recommended on a server)
Environment=FAP_PROFILE=alice

# 2) Cho đúng 1 lệnh · for a single command (bash)
FAP_PROFILE=alice fap whoami
```

```powershell
# 3) Windows PowerShell — cho phiên hiện tại · for the current session
$env:FAP_PROFILE = "alice"; fap whoami
```

**VI —** Máy chỉ phục vụ **một** profile (ví dụ laptop của Alice) thì cứ ghi `FAP_PROFILE=alice` thẳng trong `.env` ở gốc repo — bộ nạp `fapc/__init__.py` **cố ý đọc `FAP_PROFILE` từ `.env` gốc trước**, rồi mới nạp `.env.alice`, nên đường dẫn và cấu hình luôn khớp nhau.
**EN —** If a machine serves **one** profile only (e.g. Alice's laptop), just put `FAP_PROFILE=alice` in the root `.env` — the loader in `fapc/__init__.py` **deliberately peeks `FAP_PROFILE` out of the root `.env` first**, then loads `.env.alice`, so paths and config can never disagree.

---

## 2. Trạng thái nằm ở đâu · Where per-profile state lives

```
fap-cli/
├── .env                     ← của CHỦ MÁY · the owner's
├── .env.alice               ← của alice (KHÔNG commit) · alice's (never commit)
├── credentials.json         ← DÙNG CHUNG: OAuth client Google của ứng dụng · SHARED app-level Google OAuth client
└── output/
    ├── token.json …         ← profile mặc định · the default profile
    └── profiles/
        └── alice/
            ├── token.json               fap login / fap refresh
            ├── oauth_tokens.json        refresh_token (0600)
            ├── .pkce_state.json         tạm, 1 lần · transient, single-use
            ├── grade_state.json         baseline watch-grades
            ├── attendance_state.json    baseline watch-attendance
            ├── seen_notifications.json  baseline notify
            ├── subjects_catalog.json    cache
            ├── gcal_token.json          token Google Calendar RIÊNG · per-profile Google token
            ├── lichhoc.ics / lichthi.ics
            ├── local_data.json
            └── api/*.json               fap extract (0600 — học phí, hồ sơ, CCCD · fees, profile, ID card)
```

**VI —** `credentials.json` (client OAuth của **ứng dụng**, không phải của người dùng) và `.env*` nằm ở **gốc repo**, dùng chung. Log của script deploy (`output/deploy.log`) cũng vẫn ở `output/` vì đó là script shell, không biết profile.
**EN —** `credentials.json` (the **app's** OAuth client, not a user's) and the `.env*` files stay at the **repo root** and are shared. Deploy-script logs (`output/deploy.log`) also stay in `output/` — those are shell wrappers, they know nothing about profiles.

---

## 3. File cấu hình của profile · The per-profile env file

**VI —** Mỗi profile có **một file env riêng ở gốc repo**: `.env.<tên>` (ví dụ `.env.alice`). Thứ tự nạp:
**EN —** Each profile gets **its own env file at the repo root**: `.env.<name>` (e.g. `.env.alice`). Load order:

1. `.env.alice` — **nạp trước ⇒ THẮNG** (bộ nạp dùng `setdefault`) · loaded first ⇒ **wins**
2. `.env` gốc — chỉ bù các khóa **không mang danh tính** · the root `.env`, but **only** for non-identity keys

### 🔒 Khóa KHÔNG BAO GIỜ được thừa kế · Keys that are never inherited

`FAP_PROFILE` · `TELEGRAM_TOKEN` · `TELEGRAM_CHAT` · `DISCORD_WEBHOOK_URL` · `DISCORD_BOT_TOKEN` · `DISCORD_ALLOWED_USER_ID` · `DISCORD_ALLOW_ANYONE` · `GCAL_CALENDAR_ID` · `FAP_ALLOW_UPDATE`

**VI —** Profile nào **không tự khai** một khóa gửi thì kênh đó **TẮT HẲN** — đó là **thiết kế, không phải bug**. Thà không gửi còn hơn bắn điểm của alice vào chat của chủ máy.
**EN —** A profile that **doesn't declare** a delivery key simply has that channel **switched off** — that is **by design, not a bug**. Silence beats pushing alice's marks into the owner's chat.

**VI —** Các khóa **thuộc về máy** thì vẫn thừa kế từ `.env` gốc: `FAP_LANG`, `FAP_SEMESTER`, `FAP_TOKEN_READONLY`, `FAP_REMIND_MINUTES`, `FAP_AUTOUPDATE_MIN`, `FAP_WATCH_ABSENT_ONLY`, `FAP_CACHE_MIN`, `FAP_EXTRACT_DELAY`, `FAP_TOTAL_CREDITS`. Muốn khác? Khai đè trong `.env.<tên>`.
**EN —** **Machine-level** keys are still inherited from the root `.env`: `FAP_LANG`, `FAP_SEMESTER`, `FAP_TOKEN_READONLY`, `FAP_REMIND_MINUTES`, `FAP_AUTOUPDATE_MIN`, `FAP_WATCH_ABSENT_ONLY`, `FAP_CACHE_MIN`, `FAP_EXTRACT_DELAY`, `FAP_TOTAL_CREDITS`. Want a different value? Override it in `.env.<name>`.

> ⚠️ **VI —** `FAP_SEMESTER` **có** thừa kế. Chủ máy ép `FAP_SEMESTER=Spring2026` thì profile khách cũng bị ép theo (chỉ sai *khung thời gian* của dữ liệu **chính họ**, không rò dữ liệu). Để trống ở `.env` gốc là an toàn nhất.
> ⚠️ **EN —** `FAP_SEMESTER` **is** inherited. If the owner forces `FAP_SEMESTER=Spring2026`, guest profiles are forced too (it only skews the *time window* of **their own** data — nothing leaks). Leaving it empty in the root `.env` is safest.

### 🔒 `.env.<tên>` đã được gitignore sẵn · already gitignored

**VI —** `.gitignore` của repo **đã có sẵn** `.env.*` + `!.env.example`, nên `.env.alice` không bao giờ lọt vào commit (dòng `.env` trần chỉ khớp đúng tên `.env`, nên cần thêm pattern đó — đã thêm rồi). `!.env.example` giữ cho file mẫu vẫn được git theo dõi.
**EN —** The repo's `.gitignore` **already ships** `.env.*` + `!.env.example`, so `.env.alice` can never be committed (a bare `.env` line matches only that exact name, hence the extra pattern). `!.env.example` keeps the template tracked.

Vẫn nên kiểm tra một lần · verify once:

```bash
git check-ignore -v .env.alice
```

**VI —** Phải in ra luật khớp. `deploy/setup-profile.sh` cũng tự kiểm và **dừng hẳn** nếu file không được ignore.
**EN —** It must print the matching rule. `deploy/setup-profile.sh` checks this too and **aborts** if the file is not ignored.

---

## 4. Thêm một người · Onboarding a second person

**VI —** Làm **theo đúng thứ tự**. Bước 1 là bước quan trọng nhất và **không phải bước kỹ thuật**.
**EN —** Follow **this exact order**. Step 1 matters most and is **not a technical step**.

### Bước 1 — Nói rõ và được đồng ý · Get informed consent

**VI —** Nói thẳng với họ: *"`refresh_token` FAP của bạn sẽ nằm trên server của mình cho tới khi bạn đăng nhập lại nơi khác hoặc thu hồi. Mình không thấy mật khẩu của bạn, nhưng công cụ trên server mình đọc được dữ liệu FAP của bạn (điểm, điểm danh, học phí, hồ sơ)."* Không đồng ý ⇒ dừng ở đây, họ tự chạy fap-cli trên máy họ.
**EN —** Say it plainly: *"Your FAP `refresh_token` will sit on my server until you log in elsewhere or revoke it. I never see your password, but the tool on my box can read your FAP data (marks, attendance, fees, profile)."* No agreement ⇒ stop here; they run fap-cli on their own machine instead.

### Bước 2 — Kênh gửi của **họ** · Their own delivery channel

```bash
# Ở gốc repo · at the repo root
cp .env.example .env.alice
$EDITOR .env.alice     # alice tự điền TELEGRAM_TOKEN / TELEGRAM_CHAT (hoặc DISCORD_*) CỦA CHÍNH ALICE
chmod 600 .env.alice
```

**VI —** `.env.alice` **phải** chứa đầy đủ `TELEGRAM_*` / `DISCORD_*` của alice. Bỏ trống = alice không nhận được gì (chứ **không** rơi về chat của bạn).
**EN —** `.env.alice` **must** carry alice's own `TELEGRAM_*` / `DISCORD_*`. Leave them empty and alice simply gets nothing (it does **not** fall back to your chat).

### Bước 3 — **Alice tự** đăng nhập · **Alice** logs in, herself

```bash
# TRÊN MÁY CÓ TRÌNH DUYỆT, alice tự gõ · ON A MACHINE WITH A BROWSER, typed by alice
FAP_PROFILE=alice fap login
# Trình duyệt báo "scheme ... not registered" là BÌNH THƯỜNG — copy URL rồi:
FAP_PROFILE=alice fap exchange "io.identityserver.demo:/oauthredirect?code=...&state=..."
FAP_PROFILE=alice fap whoami      # phải ra mã SV của ALICE · must show ALICE's roll number
```

**VI —** Server headless không mở được trình duyệt. Nếu alice login trên máy khác, **chỉ copy `token.json` + `oauth_tokens.json`** sang `output/profiles/alice/` rồi `chmod 600` — và đọc kỹ [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines): **chỉ MỘT máy được refresh**. Ràng buộc đó áp dụng cho **từng profile**, và với profile của người khác thì **họ không tự sửa được** khi hỏng.
**EN —** A headless server can't open a browser. If alice logs in elsewhere, **copy only `token.json` + `oauth_tokens.json`** into `output/profiles/alice/`, then `chmod 600` — and read [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines): **exactly one machine may refresh**. That rule applies **per profile**, and when someone else's profile breaks, **they can't fix it themselves**.

### Bước 4 — Kiểm tra trước khi dựng service · Verify before wiring services

```bash
FAP_PROFILE=alice fap doctor     # token.json của profile này đã có chưa · this profile's token
FAP_PROFILE=alice fap refresh    # refresh headless chạy được chưa · headless refresh works
FAP_PROFILE=alice fap status     # dữ liệu ra đúng người chưa · right person's data
ls output/profiles/alice/        # KHÔNG được thấy file mới nào trong output/ gốc · nothing new in plain output/
```

### Bước 5 — Dựng service riêng · Wire up her own services

**VI —** Xem [§5](#5-mỗi-profile-một-unit-systemd--one-systemd-unit-per-profile) ngay dưới.
**EN —** See [§5](#5-mỗi-profile-một-unit-systemd--one-systemd-unit-per-profile) below.

### Bước 6 — Gỡ khi họ dừng · Off-boarding

```bash
bash deploy/setup-profile.sh --remove alice   # tắt + gỡ service của alice · stop & remove alice's units
rm -rf output/profiles/alice .env.alice       # xóa token + cấu hình của alice · delete her token & config
```

**VI —** Bảo alice **thu hồi quyền** ở phía Google/FE Identity nữa cho chắc.
**EN —** Also have alice **revoke the grant** on the Google/FE Identity side.

---

## 5. Mỗi profile một unit systemd · One systemd unit per profile

**VI —** `deploy/` có sẵn **unit mẫu (template)** dạng `<tên>@.service` — systemd thay `%i` bằng phần sau dấu `@`, và unit đặt `Environment=FAP_PROFILE=%i`. Cài **một** file mẫu, chạy **bao nhiêu profile cũng được**.
**EN —** `deploy/` ships **systemd template units** named `<name>@.service` — systemd substitutes `%i` with whatever follows the `@`, and the unit sets `Environment=FAP_PROFILE=%i`. Install the template **once**, run **as many profiles as you like**.

| Unit mẫu · Template | Chạy · Runs |
|---|---|
| `fap@.service` + `fap@.timer` | job hằng ngày: `refresh` → `calendar-sync` → `notify today` · daily one-shot |
| `fap-watch@.service` | `watch-attendance loop 15` (thường trú · resident) |
| `fap-gradewatch@.service` | `watch-grades loop 60` (thường trú · resident) |
| `fap-bot@.service` | `telegram-bot` (thường trú · resident) |

### Cách nhanh · The quick way

```bash
bash deploy/setup-profile.sh alice                        # watcher điểm danh + điểm
UNITS='watch,grades,daily' bash deploy/setup-profile.sh alice
UNITS='watch,grades,bot'   bash deploy/setup-profile.sh alice     # + bot Telegram riêng của alice
bash deploy/setup-profile.sh --remove alice               # gỡ · remove
```

**VI —** Script **từ chối chạy** nếu chưa có `output/profiles/alice/token.json` (alice chưa tự login) — cố tình như vậy.
**EN —** The script **refuses to run** when `output/profiles/alice/token.json` is missing (alice hasn't logged in yet) — deliberately.

### Cách thủ công · By hand

```bash
sed -e "s#%h/fap-cli#$PWD#g" -e "s#%h/.venv/bin/fap#$PWD/.venv/bin/fap#g" \
    deploy/fap-watch@.service > ~/.config/systemd/user/fap-watch@.service
systemctl --user daemon-reload
systemctl --user enable --now fap-watch@alice.service
systemctl --user status  fap-watch@alice.service
journalctl --user -u fap-watch@alice.service -n 50 -f
```

**VI —** Profile **mặc định** (chủ máy) vẫn dùng unit không có `@` như trước: `fap-watch.service`, `fap-gradewatch.service`, `fap-bot.service`, `fap.timer`. Hai loại chạy song song thoải mái.
**EN —** The **default** profile (the owner) keeps the plain non-`@` units as before: `fap-watch.service`, `fap-gradewatch.service`, `fap-bot.service`, `fap.timer`. Both kinds coexist happily.

**VI —** `bash deploy/update.sh` khởi động lại **cả** unit thường trú mặc định **lẫn** mọi instance `fap-*@<tên>.service` đang bật, nên cập nhật code là mọi profile cùng nạp mã mới.
**EN —** `bash deploy/update.sh` restarts **both** the default resident units **and** every enabled `fap-*@<name>.service` instance, so one update reloads the code for every profile.

### Windows

**VI —** Windows không có systemd và Scheduled Task không tiện gắn biến môi trường. Cách thực dụng: **một máy Windows phục vụ một profile** — ghi `FAP_PROFILE=alice` vào `.env` ở gốc repo, rồi đăng ký task như bình thường (`deploy\register-watch-windows.ps1`). Bộ nạp đọc `FAP_PROFILE` từ `.env` gốc nên task chạy đúng profile.
**EN —** Windows has no systemd, and Scheduled Tasks make env vars awkward. Pragmatic route: **one Windows box serves one profile** — put `FAP_PROFILE=alice` in the root `.env`, then register the task as usual (`deploy\register-watch-windows.ps1`). The loader reads `FAP_PROFILE` from the root `.env`, so the task runs under the right profile.

---

## 6. ⚠️ Cạm bẫy · Traps

### 6.1 🔴 Khóa gửi không được thừa kế — và đó là điều TỐT · A missing delivery key must not fall back

**VI —** Trước đây có **hai** bộ nạp `.env` độc lập; bộ thứ hai bơm lại `TELEGRAM_CHAT` của chủ máy vào profile khách ⇒ **điểm của alice bắn vào chat của chủ máy**. Nay chỉ còn **một** bộ nạp và các khóa danh tính bị **chặn cứng**. Hệ quả bạn phải nhớ: **profile im lặng = profile thiếu khóa gửi**, không phải "notify hỏng". Kiểm tra `.env.<tên>` trước khi đi tìm bug.
**EN —** There used to be **two** independent `.env` loaders; the second one re-injected the owner's `TELEGRAM_CHAT` into a guest profile ⇒ **alice's marks landed in the owner's chat**. There is now **one** loader and identity keys are **hard-blocked**. The consequence to remember: **a silent profile means a missing delivery key**, not "notify is broken". Check `.env.<name>` before hunting bugs.

### 6.2 🔴 Google Calendar dùng chung · Sharing one Google Calendar

**VI —** Trước đây `calendar-prune` chạy dưới profile A **xóa sạch cả kỳ của profile B** (`iCalUID` không chứa mã SV, bộ lọc chỉ có `fapc=1`). Đã sửa:
**EN —** `calendar-prune` under profile A used to **delete profile B's entire semester** (`iCalUID` carried no roll number; the filter was just `fapc=1`). Now fixed:

- **VI —** Mọi sự kiện fap-cli tạo đều mang **dấu chủ sở hữu = mã sinh viên**: nhãn riêng `fapc_owner=<mã SV>` + `iCalUID` dạng `fapc-<mã SV>-<ngày>-<môn>-<slot>@fap.fpt.edu.vn`.
  **EN —** Every event fap-cli creates carries an **owner tag = the roll number**: private property `fapc_owner=<roll>` plus an `iCalUID` of the form `fapc-<roll>-<date>-<subject>-<slot>@fap.fpt.edu.vn`.
- **VI —** `calendar-prune`/`--prune` **chỉ liệt kê và chỉ xóa** sự kiện mang **mã SV của chính mình** ⇒ dùng chung một lịch Google giữa nhiều profile là **an toàn**.
  **EN —** `calendar-prune`/`--prune` **only lists and only deletes** events tagged with **its own roll number** ⇒ sharing one Google calendar across profiles is **safe**.
- **VI —** Sự kiện **cũ chưa có nhãn** (tạo bởi bản fap-cli trước) chỉ thuộc về **profile mặc định**. Profile có tên **không bao giờ** đụng vào chúng; profile mặc định "nhận nuôi" chúng và **cập nhật tại chỗ** (giữ nguyên `iCalUID` cũ) nên **không nhân đôi, không xóa để tạo lại**.
  **EN —** **Untagged legacy events** (written by an older fap-cli) belong to the **default profile only**. A named profile **never** touches them; the default profile adopts them and **updates them in place** (keeping the old `iCalUID`) — **no duplicates, no delete-and-recreate**.
- **VI —** Mỗi profile phải **tự chạy `fap calendar-auth` một lần** (token Google nằm ở `output/profiles/<tên>/gcal_token.json`). `credentials.json` ở gốc repo là **dùng chung**.
  **EN —** Each profile must run **`fap calendar-auth` once** (its Google token lives at `output/profiles/<name>/gcal_token.json`). The root `credentials.json` is **shared**.
- ⚠️ **VI —** `GCAL_CALENDAR_ID` **không thừa kế**, nhưng mặc định vẫn là `primary`. Nếu hai profile xác thực **cùng một tài khoản Google** thì cả hai ghi vào **cùng một lịch** — an toàn (không xóa nhầm nhau) nhưng **lịch bị trộn**. Muốn tách: tạo lịch riêng rồi đặt `GCAL_CALENDAR_ID=<id>` trong `.env.<tên>`.
  ⚠️ **EN —** `GCAL_CALENDAR_ID` is **not inherited**, but its default is still `primary`. If two profiles authorize the **same Google account**, both write to the **same calendar** — safe (neither prunes the other) but **visually mixed**. To separate them, create a dedicated calendar and set `GCAL_CALENDAR_ID=<id>` in `.env.<name>`.
- **VI —** Còn một rủi ro **không sửa được từ phía bạn**: một người dùng chung lịch nhưng vẫn chạy **bản fap-cli CŨ** thì sự kiện của họ không có nhãn ⇒ `calendar-prune` của **profile mặc định** vẫn có thể coi là mồ côi. Cách xử lý: bảo họ cập nhật.
  **EN —** One residual risk you **cannot fix from your side**: someone sharing the calendar while still running an **old fap-cli** produces untagged events, which the **default profile's** prune may still treat as orphans. The fix is for them to update.

### 6.3 🔴 `refresh_token` của mỗi người nằm trên server CỦA BẠN · Everyone's refresh token lives on YOUR server

**VI —** Đây là hệ quả **không né được** của multi-profile: `output/profiles/alice/oauth_tokens.json` là **chìa khóa dài hạn** vào dữ liệu FAP của alice, và nó nằm trên máy bạn. Quyền file: `token.json`, `oauth_tokens.json`, `gcal_token.json`, `attendance_state.json`, `seen_notifications.json`, `api/*.json`, `local_data.json` được ghi với mode `0600`; **`grade_state.json` thì CHƯA** (nó chứa điểm — nếu máy có nhiều user Linux, hãy `chmod 700 output/profiles/<tên>`; `deploy/setup-profile.sh` tự làm việc này). Kèm theo:
**EN —** This is the **unavoidable** consequence of multi-profile: `output/profiles/alice/oauth_tokens.json` is a **long-lived key** to alice's FAP data and it sits on your box. File modes: `token.json`, `oauth_tokens.json`, `gcal_token.json`, `attendance_state.json`, `seen_notifications.json`, `api/*.json` and `local_data.json` are written `0600`; **`grade_state.json` is not yet** (it holds marks — on a multi-user box, `chmod 700 output/profiles/<name>`; `deploy/setup-profile.sh` does that for you). It follows that:

- **VI —** Alice phải **đồng ý rõ ràng** (Bước 1) — đây là chuyện **con người**, không phải chuyện kỹ thuật.
  **EN —** Alice must give **explicit consent** (Step 1) — a **human** matter, not a technical one.
- **VI —** Backup server của bạn giờ chứa PII của người khác. Đừng đẩy `output/` lên nơi dùng chung; `output/` đã `.gitignore` — giữ nguyên như thế.
  **EN —** Your server backups now hold someone else's PII. Never push `output/` anywhere shared; it is `.gitignore`d — keep it that way.
- **VI —** `fap extract` của alice ghi học phí, hồ sơ, số CCCD vào `output/profiles/alice/api/*.json`. Chỉ chạy khi alice thực sự cần.
  **EN —** Alice's `fap extract` writes fees, profile data and ID-card numbers to `output/profiles/alice/api/*.json`. Only run it when alice actually needs it.
- **VI —** Đúng **MỘT** nơi được refresh token của alice. Alice cũng copy token về laptop và chạy `fap refresh` ở đó ⇒ đua rotation, token trên server chết, và **alice không tự sửa được**. Xem [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) — doctrine đó áp dụng cho **từng profile**.
  **EN —** Exactly **ONE** place may refresh alice's token. If alice also copies it to her laptop and runs `fap refresh` there, the rotation race kills the server's copy and **alice can't fix it**. See [14-deploy §9](14-deploy.md#9-một-session-hai-máy--one-session-two-machines) — that doctrine is **per profile**.

### 6.4 `/update` chạy trên checkout DÙNG CHUNG · `/update` acts on the SHARED checkout

**VI —** Lệnh bot `/update` làm `git pull` + tự khởi động lại trên **checkout mà mọi profile dùng chung**. Vì vậy nó **TẮT mặc định**: phải có `FAP_ALLOW_UPDATE=1` mới chạy, và chỉ đặt trong **unit của chủ máy** — **đừng** đặt trong `.env.<tên>` của khách (khóa này cũng nằm trong danh sách không-thừa-kế). Chủ sở hữu bot vẫn được kiểm tra trước như cũ.
**EN —** The bot's `/update` runs `git pull` + self-restart on the **checkout every profile shares**. So it is **off by default**: it needs `FAP_ALLOW_UPDATE=1`, set only in the **owner's unit** — **never** in a guest's `.env.<name>` (that key is on the never-inherited list too). The existing owner-only check still runs first.

### 6.5 `subjects_catalog.json` để riêng từng profile · Per-profile subject catalog

**VI —** Cache danh mục môn học **không** dùng chung (dữ liệu nhỏ, tra theo `campusCode`) — profile khác campus vẫn ra đúng dữ liệu, đổi lại mỗi profile tự dựng cache một lần.
**EN —** The subject-catalog cache is **not** shared (it's small and keyed by `campusCode`) — a profile at another campus still gets correct data, at the cost of building its cache once.

---

## 7. Kiểm tra nhanh · Quick checks

| Muốn biết · Question | Lệnh · Command |
|---|---|
| Profile nào đang chạy? · Which profile is active? | `FAP_PROFILE=alice fap whoami` → mã SV phải là của alice · the roll must be alice's |
| Token của profile có chưa? · Does this profile have a token? | `FAP_PROFILE=alice fap doctor` |
| Có ghi nhầm ra `output/` gốc không? · Anything leaking into plain `output/`? | `ls -la output/ output/profiles/alice/` |
| `.env.<tên>` đã bị gitignore chưa? · Is it ignored? | `git check-ignore -v .env.alice` |
| Service của alice sống không? · Is alice's unit alive? | `systemctl --user status fap-watch@alice.service` |

---

> ⚠️ **VI —** Dự án KHÔNG chính thức, chỉ dùng cho dữ liệu của chính bạn — và với multi-profile là dữ liệu của người đã **đồng ý rõ ràng**. Đọc [../SECURITY.md](../SECURITY.md).
> **EN —** Unofficial project, your own data only — and, with multi-profile, data belonging to people who have **explicitly consented**. Read [../SECURITY.md](../SECURITY.md).
