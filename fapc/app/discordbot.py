#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discordbot.py — Bot Discord TƯƠNG TÁC (discord.py, optional extra [bot]).

    pip install -e ".[bot]"
    fap discord-bot          # chạy nền, trả lời lệnh prefix `!` (vd !today, !grades)

Cần: DISCORD_BOT_TOKEN (Developer Portal → Bot → Token) trong .env, và bật quyền
"MESSAGE CONTENT INTENT" cho bot. Bảo mật: nếu đặt DISCORD_ALLOWED_USER_ID thì CHỈ trả lời
user đó (khuyến nghị mạnh — tránh lộ dữ liệu). Prefix mặc định `!`. Xem docs/13-notify.md.

Trả lời NGẮN đi bằng **embed** (tiêu đề + thân), dài thì vẫn cắt mẩu plain-text như cũ.
`!menu` / `/menu` đăng một **bảng nút bấm** sinh từ bot_core.menu_commands(); nút kiểm quyền
y hệt lệnh gõ tay, người ngoài bấm nhận lời từ chối RIÊNG (ephemeral).
"""
import asyncio, os, time
from .. import config, fmt
from .bot_core import handle, menu_commands
from . import botgcal
from .reminders import ClassReminder
from .selfupdate import perform_update, restart, maybe_autoupdate, autoupdate_min, owner_checkout
from ..i18n import t

PREFIX = "!"
# Trần MỘT tin của Discord là 2000 — chừa biên an toàn. Tin dài hơn được CẮT THÀNH NHIỀU MẨU
# (fmt.chunks) rồi gửi lần lượt; KHÔNG cắt cụt bằng [:N] làm mất chữ (vd /grades-detail 5325 ký tự).
LIMIT = 1900
_GAP  = 0.4     # giây nghỉ giữa 2 mẩu — nhẹ tay với API (số mẩu rất nhỏ: 2–3)

# Embed: trần `description` là 4096 (KHÁC trần 2000 của `content`) — chừa biên an toàn.
# Câu trả lời vừa khuôn này đi đường embed (đẹp, 1 tin); dài hơn LÙI VỀ đường chunks plain-text.
EMBED_LIMIT = 4000
TITLE_LIMIT = 250       # trần title của embed là 256

# Nút bấm: Discord cho TỐI ĐA 5 nút/hàng × 5 hàng = 25 nút cho MỘT view.
BTN_PER_ROW = 5
BTN_ROWS    = 5
MAX_BUTTONS = BTN_PER_ROW * BTN_ROWS

async def _send_chunks(send, text, view=None):
    """Gửi `text` qua coroutine `send(str)` thành NHIỀU mẩu ≤ LIMIT. True chỉ khi MỌI mẩu đã tới nơi.

    `view` (bảng nút) CHỈ gắn vào mẩu CUỐI — gắn vào mọi mẩu sẽ ra 3 bảng nút trùng nhau.
    Gửi dở (mẩu đầu tới nơi, mẩu sau hỏng) -> cảnh báo ra log và trả False: người đọc đang thiếu chữ."""
    parts = fmt.chunks(text, LIMIT)
    for i, part in enumerate(parts):
        if i:
            await asyncio.sleep(_GAP)
        kw = {"view": view} if (view is not None and i == len(parts) - 1) else {}
        try:
            await send(part, **kw)
        except Exception as e:                       # noqa: BLE001 — 1 mẩu hỏng không được làm chết bot
            print(f"  gửi lỗi · send error: {e}")
            if i:
                print(t(f"  ⚠️ mới gửi {i}/{len(parts)} mẩu — phần còn lại CHƯA tới nơi.",
                        f"  ⚠️ only {i}/{len(parts)} chunks sent — the rest did NOT arrive."))
            return False
    return True

def _embed(text):
    """Dựng `discord.Embed` cho câu trả lời NGẮN: dòng đầu -> title, phần còn lại -> description
    (bỏ đường kẻ `fmt.RULE` vì embed đã có khung riêng).

    Trả None khi KHÔNG dựng được — caller phải lùi về `_send_chunks` (cắt mẩu), TUYỆT ĐỐI không cắt cụt:
      · chưa cài discord.py (module này phải import được khi thiếu dep — xem tests/integration_offline.py)
      · text rỗng / chỉ có 1 dòng / tiêu đề dài quá TITLE_LIMIT
      · text dài hơn EMBED_LIMIT (4096 của Discord, đã chừa biên)
    `import discord` để TRONG hàm — cố ý LƯỜI."""
    try:
        import discord
    except ImportError:
        return None
    text = "" if text is None else str(text)
    if not text.strip() or len(text) > EMBED_LIMIT:
        return None
    lines = text.split("\n")
    title = lines[0].strip()
    body  = lines[1:]
    if body and body[0].strip() == fmt.RULE:
        body = body[1:]
    body = "\n".join(body).strip()
    if not body or not title or len(title) > TITLE_LIMIT:
        return None
    try:
        return discord.Embed(title=title, description=body)
    except Exception:                                # noqa: BLE001 — dựng embed hỏng -> đi đường plain-text
        return None

async def _send_rich(send, text, view=None):
    """Trả lời NGẮN -> 1 embed gọn gàng; DÀI (hoặc thiếu discord.py) -> đường chunks plain-text như cũ.
    Không bao giờ mất chữ: `_embed` trả None thay vì cắt cụt, và embed gửi hỏng thì thử lại plain-text."""
    em = _embed(text)
    if em is not None:
        kw = {"view": view} if view is not None else {}
        try:
            await send(embed=em, **kw)
            return True
        except Exception as e:                       # noqa: BLE001 — embed hỏng thì vẫn phải giao được chữ
            print(f"  gửi embed lỗi · embed send error: {e}")
    return await _send_chunks(send, text, view=view)

def _denied_msg():
    return t("⛔ Nút này chỉ dành cho chủ bot · không có quyền.",
             "⛔ This button is for the bot owner only · not allowed.")

def _update_allowed():
    """/update chạy `git pull` + restart trên CHECKOUT DÙNG CHUNG → phải bật rõ ràng ở máy chủ.
    Đọc config.ALLOW_UPDATE (FAP_ALLOW_UPDATE); config.py có thể chưa khai báo → lùi về env.
    Chạy dưới profile KHÁCH -> luôn CẤM (khách không được động vào checkout dùng chung)."""
    if not owner_checkout():
        return False
    v = getattr(config, "ALLOW_UPDATE", None)
    if v is None:
        v = os.environ.get("FAP_ALLOW_UPDATE")
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")

def _update_off_msg():
    return t("⛔ /update đang TẮT trên máy này. Bật bằng FAP_ALLOW_UPDATE=1 trong .env — chỉ đặt trên "
             "checkout của chủ máy, vì git pull + khởi động lại ảnh hưởng MỌI profile dùng chung mã nguồn.",
             "⛔ /update is DISABLED on this host. Enable it with FAP_ALLOW_UPDATE=1 in .env — owner's "
             "checkout only, since git pull + restart affects EVERY profile sharing this source tree.")

def run():
    try:
        import discord
    except ImportError:
        raise SystemExit('Thiếu discord.py. Cài: pip install -e ".[bot]"  (cần Python ≥ 3.8)')
    if not config.DISCORD_BOT_TOKEN:
        raise SystemExit("Thiếu DISCORD_BOT_TOKEN trong .env (Developer Portal → Bot → Reset Token).")
    allow = str(config.DISCORD_ALLOWED_USER_ID) if config.DISCORD_ALLOWED_USER_ID else None
    if not allow:
        if os.environ.get("DISCORD_ALLOW_ANYONE") not in ("1", "true", "True"):
            raise SystemExit("Thiếu DISCORD_ALLOWED_USER_ID trong .env — BẮT BUỘC, để bot CHỈ trả lời bạn "
                             "(tránh lộ điểm/lịch). Cố tình mở cho mọi người: đặt DISCORD_ALLOW_ANYONE=1.")
        print("⚠️  DISCORD_ALLOW_ANYONE=1 — bot MỞ cho mọi user; dữ liệu của bạn sẽ lộ cho ai gõ lệnh.")

    intents = discord.Intents.default()
    intents.message_content = True          # cần bật ở Developer Portal (privileged intent)
    # Không bao giờ ping: nội dung trả lời đến từ FAP — '@everyone' trong dữ liệu server không được thành mention.
    client = discord.Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())

    def _owner(user_id):
        """Quyền chạy lệnh — Y HỆT luật của tin nhắn/slash: có DISCORD_ALLOWED_USER_ID thì chỉ chủ bot;
        chế độ MỞ (DISCORD_ALLOW_ANYONE, allow=None) thì ai cũng được. Nút bấm dùng CHUNG hàm này để
        không bao giờ lệch khỏi lệnh gõ tay."""
        return (not allow) or str(user_id) == allow

    async def _run(name, arg=None):
        """Chạy handle() NGOÀI event loop (HTTP đồng bộ tới 25s) và nuốt lỗi thành text trả lời."""
        try:
            return await client.loop.run_in_executor(None, handle, name, arg)
        except SystemExit as e:
            return str(e)
        except Exception as e:                            # noqa: BLE001 — 1 lệnh lỗi không làm chết bot
            return f"Lỗi · error: {e}"

    def _calendar_text(name, arg):
        """BLOCKING (gọi trong run_in_executor): chạy MỘT lệnh calendar-* và trả CHUỖI. Nuốt lỗi thành
        chữ. Bước đăng nhập KHÔNG in token (gcal.gcal_auth_finish chỉ trả câu xác nhận)."""
        from . import gcal
        key = (name or "").lower().replace("_", "-")
        arg = (arg or "").strip()
        try:
            if key == "calendar-auth":
                url, label = gcal.gcal_auth_url(arg)
                where = label or t("mặc định", "default")
                return "\n".join([
                    t(f"🔗 Cài Google Calendar cho đích '{where}'. Mở link, đăng nhập Google:",
                      f"🔗 Set up Google Calendar for '{where}'. Open the link and sign in to Google:"),
                    url,
                    t("Trình duyệt sẽ báo “không kết nối được 127.0.0.1” — ĐÚNG rồi. Copy URL trên thanh địa "
                      "chỉ rồi chạy:  /calendar-auth-finish <URL>  (câu trả lời chỉ mình bạn thấy).",
                      "The browser will say “can't reach 127.0.0.1” — that's fine. Copy the address-bar URL "
                      "then run:  /calendar-auth-finish <URL>  (the reply is visible only to you)."),
                ])
            if key in ("calendar-auth-finish", "calendar-finish"):
                if not arg:
                    return t("Dán URL redirect sau lệnh: /calendar-auth-finish <URL>",
                             "Paste the redirect URL after the command: /calendar-auth-finish <URL>")
                return gcal.gcal_auth_finish(arg)
            if key == "calendar-sync":
                label, prune, yes, force = botgcal.parse_sync_args(arg)
                return gcal.sync_text(label, prune=prune, yes=yes, force=force)
            if key == "calendar-prune":
                label, _p, yes, force = botgcal.parse_sync_args(arg)
                return gcal.prune_text(label, yes=yes, force=force)
            if key in ("calendar-list", "calendars", "calendar"):
                return gcal.destinations_text()
            if key == "calendar-add":
                parts = arg.split(None, 1)
                return gcal.add_destination(parts[0] if parts else "", parts[1] if len(parts) > 1 else "")
            if key == "calendar-remove":
                return gcal.remove_destination(arg)
        except SystemExit as e:
            return str(e)
        except Exception as e:                            # noqa: BLE001
            return f"Lỗi calendar · error: {e}"
        return None

    _view_memo = {}                                       # dựng MỘT LẦN rồi dùng lại (xem _make_view)

    def _make_view():
        """Bảng nút bấm — sinh TỪ bot_core.menu_commands() (NGUỒN DUY NHẤT, không chép tay lần 2).
        Cắt còn MAX_BUTTONS=25 nút (trần 5 nút × 5 hàng của Discord); lệnh dôi ra vẫn gõ tay được.
        Callback kiểm quyền BẰNG `_owner` — người ngoài bấm sẽ bị từ chối RIÊNG (ephemeral).

        MEMO HOÁ: discord.py chỉ gỡ một View khỏi ViewStore khi View.stop()/hết timeout, mà đây là
        timeout=None → mỗi lần gõ !menu lại nhét thêm 25 nút vào store và chúng ở đó tới hết đời tiến
        trình. Dựng 1 lần, gửi lại CÙNG một instance (đúng cách persistent view của discord.py)."""
        if _view_memo.get("v") is not None:
            return _view_memo["v"]
        import discord                                    # LƯỜI: module phải import được khi thiếu dep
        view = discord.ui.View(timeout=None)              # timeout=None + custom_id -> nút sống lâu dài
        for i, (name, _desc) in enumerate(menu_commands()[:MAX_BUTTONS]):
            btn = discord.ui.Button(label=name.replace("_", "-")[:80],
                                    style=discord.ButtonStyle.secondary,
                                    custom_id=("fap:" + name)[:100],
                                    row=i // BTN_PER_ROW)

            async def _cb(interaction, _n=name):          # _n=name: khoá tên lệnh vào từng nút
                if not _owner(interaction.user.id):
                    await interaction.response.send_message(_denied_msg(), ephemeral=True)
                    return
                await interaction.response.defer(thinking=True)   # ack <3s; handle() có thể tốn tới 25s
                await _send_rich(interaction.followup.send, await _run(_n))
            btn.callback = _cb
            view.add_item(btn)
        _view_memo["v"] = view
        return view

    def _menu_text():
        n = len(menu_commands()[:MAX_BUTTONS])
        return fmt.header("🎛️", t("Bảng lệnh nhanh", "Quick command panel"),
                          t(f"{n} lệnh", f"{n} commands")) + "\n" + t(
            "Bấm một nút để chạy lệnh ngay. Gõ tay `!today` / `/grades` vẫn dùng được như thường.",
            "Tap a button to run a command. Typing `!today` / `/grades` still works as before.") + (
            "\n" + t("Chỉ chủ bot bấm được.", "Owner only.") if allow else "")

    # Slash command (/) — danh sách lệnh TỰ GỢI Ý khi gõ '/'. Đăng ký động từ menu_commands().
    # Bọc try/except: nếu phiên bản discord.py không có app_commands thì bot vẫn chạy prefix '!'.
    tree = None
    try:
        tree = discord.app_commands.CommandTree(client)

        def _make(name):
            async def _cmd(interaction, arg: str = None):
                if not _owner(interaction.user.id):
                    await interaction.response.send_message("⛔ Không có quyền · not allowed.", ephemeral=True)
                    return
                await interaction.response.defer(thinking=True)   # ack <3s; handle() có thể tốn tới 25s
                await _send_rich(interaction.followup.send, await _run(name, arg))
            return _cmd

        for _n, _d in menu_commands():
            tree.command(name=_n, description=(_d or _n)[:100])(_make(_n))

        async def _menu_cmd(interaction):                         # /menu — bảng nút bấm
            if not _owner(interaction.user.id):
                await interaction.response.send_message(_denied_msg(), ephemeral=True)
                return
            # _send_rich: embed nếu dựng được, không thì gửi plain-text — vẫn kèm bảng nút.
            await _send_rich(interaction.response.send_message, _menu_text(), view=_make_view())
        tree.command(name="menu",
                     description=t("Bảng nút bấm lệnh", "Command button panel")[:100])(_menu_cmd)

        async def _update_cmd(interaction):                       # /update — chỉ CHỦ tài khoản (kể cả chế độ MỞ)
            if not allow or str(interaction.user.id) != allow:    # ALLOW_ANYONE: allow=None -> vẫn CHẶN /update
                await interaction.response.send_message(
                    "⛔ /update chỉ dành cho chủ bot (đặt DISCORD_ALLOWED_USER_ID).", ephemeral=True)
                return
            if not _update_allowed():                         # checkout dùng chung -> phải bật FAP_ALLOW_UPDATE
                await interaction.response.send_message(_update_off_msg(), ephemeral=True)
                return
            await interaction.response.defer(thinking=True)
            summary, do_restart = await client.loop.run_in_executor(None, perform_update)
            await _send_rich(interaction.followup.send, summary)
            if do_restart:
                restart()                                         # thay tiến trình → quay lại với mã mới
        tree.command(name="update",
                     description=t("Cập nhật code + khởi động lại", "Update code + restart")[:100])(_update_cmd)

        # Google Calendar (loopback-paste). auth + auth-finish trả lời RIÊNG (ephemeral): URL chứa mã
        # dùng-một-lần, không để lộ ra kênh. Không xoá được tin người dùng trong DM nên dùng ephemeral.
        def _make_cal(cmd_name, ephemeral=False):
            async def _cal(interaction, arg: str = None):
                if not _owner(interaction.user.id):
                    await interaction.response.send_message("⛔ Không có quyền · not allowed.", ephemeral=True)
                    return
                await interaction.response.defer(thinking=True, ephemeral=ephemeral)
                txt = await client.loop.run_in_executor(None, _calendar_text, cmd_name, arg)
                await _send_rich(lambda *a, **k: interaction.followup.send(*a, ephemeral=ephemeral, **k),
                                 txt or t("(không có gì)", "(nothing)"))
            return _cal

        _CAL_SLASH = [
            ("calendar-auth",        t("Cài Google Calendar (đăng nhập)", "Set up Google Calendar (sign in)"), True),
            ("calendar-auth-finish", t("Hoàn tất đăng nhập: dán URL redirect", "Finish sign-in: paste redirect URL"), True),
            ("calendar-sync",        t("Đồng bộ lịch học lên Google", "Sync schedule to Google Calendar"), False),
            ("calendar-prune",       t("Dọn buổi đã hủy/dời (dry-run; 'yes' để xoá)", "Prune cancelled events (dry-run; 'yes' to delete)"), False),
            ("calendar-list",        t("Danh sách đích Google Calendar", "List Google Calendar destinations"), False),
            ("calendar-add",         t("Thêm đích: <nhãn> <calendar_id>", "Add destination: <label> <calendar_id>"), False),
            ("calendar-remove",      t("Bỏ một đích Google Calendar", "Remove a Google Calendar destination"), False),
        ]
        for _cn, _cd, _eph in _CAL_SLASH:
            tree.command(name=_cn, description=(_cd or _cn)[:100])(_make_cal(_cn, _eph))
    except Exception as e:                                        # noqa: BLE001
        print("  (slash command không khả dụng, chỉ dùng prefix '!':", e, ")")
        tree = None

    # Nhắc trước mỗi tiết — DM thẳng cho CHỦ tài khoản (cần DISCORD_ALLOWED_USER_ID). Chạy nền 60s/nhịp.
    async def _reminder_loop():
        await client.wait_until_ready()
        rem = ClassReminder()
        if not rem.enabled():
            return
        if not allow:
            print("  (⏰ nhắc lịch cần DISCORD_ALLOWED_USER_ID để DM — bỏ qua khi mở cho mọi người)")
            return
        try:
            target = await client.fetch_user(int(allow))
        except Exception as e:                                    # noqa: BLE001
            print("  (⏰ không tìm được user để DM nhắc lịch:", e, ")"); return
        print(f"  ⏰ Nhắc trước mỗi tiết {rem.lead}' (DM tới user {allow}).")
        while not client.is_closed():
            try:
                texts = await client.loop.run_in_executor(None, rem.tick)   # tick có gọi mạng -> ra khỏi event loop
                for txt in texts:
                    await _send_chunks(target.send, txt)
            except Exception as e:                                # noqa: BLE001 — nhắc lỗi không làm chết bot
                print("  ⏰ nhắc lỗi · reminder error:", e)
            await asyncio.sleep(60)

    # Tự cập nhật khi đang chạy (opt-in FAP_AUTOUPDATE_MIN>0): pull → selftest → tự khởi động lại.
    async def _autoupdate_loop():
        await client.wait_until_ready()
        last = 0.0
        while not client.is_closed():
            last = await client.loop.run_in_executor(None, maybe_autoupdate, last, time.time())
            await asyncio.sleep(60)

    _started = {"reminder": False, "autoupdate": False, "view": False}

    @client.event
    async def on_ready():
        if tree is not None:
            try:
                synced = await tree.sync()                        # đăng ký toàn cục (có thể mất tới ~1h để hiện)
                print(f"  /slash: đồng bộ {len(synced)} lệnh (gõ '/' để thấy gợi ý).")
            except Exception as e:                                # noqa: BLE001
                print("  (không sync được /slash — cần mời bot với scope 'applications.commands':", e, ")")
        if not _started["view"]:                                  # nút của bảng !menu CŨ vẫn bấm được sau khi
            _started["view"] = True                               # bot khởi động lại (vd sau /update)
            try:
                client.add_view(_make_view())
            except Exception as e:                                # noqa: BLE001 — không có nút vẫn gõ lệnh được
                print("  (không đăng ký được nút bấm bền:", e, ")")
        if not _started["reminder"]:                              # on_ready có thể bắn lại khi reconnect -> chỉ chạy 1 lần
            _started["reminder"] = True
            client.loop.create_task(_reminder_loop())
        if not _started["autoupdate"] and autoupdate_min() > 0:
            _started["autoupdate"] = True
            client.loop.create_task(_autoupdate_loop())
            print(f"  🔄 Tự cập nhật khi đang chạy: BẬT mỗi {autoupdate_min()}' (FAP_AUTOUPDATE_MIN).")
        print(f"🤖 Discord bot online: {client.user}  (prefix '{PREFIX}'"
              + (f", chỉ user {allow})" if allow else ", MỞ cho mọi user)"))

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        content = (message.content or "").strip()
        if not content.startswith(PREFIX):
            return
        if allow and str(message.author.id) != allow:
            return                              # im lặng với người ngoài allowlist (không xác nhận bot sống)
        # split(None, 1): giữ NGUYÊN phần còn lại làm tham số (như slash command và CLI).
        parts = content[len(PREFIX):].split(None, 1)
        if not parts:
            return
        cmd, arg = parts[0], (parts[1].strip() or None if len(parts) > 1 else None)
        if cmd.strip().lower() == "menu":                       # !menu — bảng nút bấm (quyền = như lệnh)
            await _send_rich(message.channel.send, _menu_text(), view=_make_view())
            return
        if cmd.strip().lower() == "update":                     # !update — chỉ CHỦ tài khoản
            if not allow or str(message.author.id) != allow:    # chế độ MỞ (allow=None): CHẶN update (tránh self-DoS pull+restart)
                await message.channel.send("⛔ /update chỉ dành cho chủ bot (đặt DISCORD_ALLOWED_USER_ID).")
                return
            if not _update_allowed():                           # checkout dùng chung -> phải bật FAP_ALLOW_UPDATE
                await message.channel.send(_update_off_msg())
                return
            await message.channel.send(t("⏳ Đang cập nhật (git pull + selftest)…", "⏳ Updating (git pull + selftest)…"))
            summary, do_restart = await client.loop.run_in_executor(None, perform_update)
            await _send_rich(message.channel.send, summary)
            if do_restart:
                restart()                                       # thay tiến trình → quay lại với mã mới
            return
        ck = cmd.strip().lower().replace("_", "-")
        if ck == "calendar" or ck.startswith("calendar-") or ck == "calendars":
            # calendar-auth-finish: URL có mã dùng-một-lần → THỬ xoá tin người dùng (được trong kênh
            # guild có quyền Manage Messages; KHÔNG được trong DM) rồi báo nếu không xoá được.
            if ck in ("calendar-auth-finish", "calendar-finish"):
                deleted = True
                try:
                    await message.delete()
                except Exception:                               # noqa: BLE001 — DM/không đủ quyền
                    deleted = False
                txt = await client.loop.run_in_executor(None, _calendar_text, ck, arg)
                if not deleted:
                    txt += "\n" + t("⚠️ Không xoá được tin chứa link — bạn tự xoá giúp (có mã đăng nhập). "
                                    "Lần sau dùng /calendar-auth-finish (ẩn) cho an toàn.",
                                    "⚠️ Couldn't delete your link message — delete it yourself (it has a sign-in "
                                    "code). Next time use /calendar-auth-finish (ephemeral) for safety.")
                await _send_rich(message.channel.send, txt)
                return
            txt = await client.loop.run_in_executor(None, _calendar_text, ck, arg)
            await _send_rich(message.channel.send, txt or t("(không có gì)", "(nothing)"))
            return
        # _run: handle() gọi HTTP ĐỒNG BỘ (tới 25s/lệnh) -> chạy trong thread executor,
        # KHÔNG chặn event loop async (giữ heartbeat gateway, bot không bị "lag"/offline).
        await _send_rich(message.channel.send, await _run(cmd, arg))

    client.run(config.DISCORD_BOT_TOKEN)

def main():
    run()

if __name__ == "__main__":
    main()
