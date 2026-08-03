#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discordbot.py — Bot Discord TƯƠNG TÁC (discord.py, optional extra [bot]).

    pip install -e ".[bot]"
    fap discord-bot          # chạy nền, trả lời lệnh prefix `!` (vd !today, !grades)

Cần: DISCORD_BOT_TOKEN (Developer Portal → Bot → Token) trong .env, và bật quyền
"MESSAGE CONTENT INTENT" cho bot. Bảo mật: nếu đặt DISCORD_ALLOWED_USER_ID thì CHỈ trả lời
user đó (khuyến nghị mạnh — tránh lộ dữ liệu). Prefix mặc định `!`. Xem docs/13-notify.md.
"""
import asyncio, os, time
from .. import config, fmt
from .bot_core import handle, menu_commands
from .reminders import ClassReminder
from .selfupdate import perform_update, restart, maybe_autoupdate, autoupdate_min, owner_checkout
from ..i18n import t

PREFIX = "!"
# Trần MỘT tin của Discord là 2000 — chừa biên an toàn. Tin dài hơn được CẮT THÀNH NHIỀU MẨU
# (fmt.chunks) rồi gửi lần lượt; KHÔNG cắt cụt bằng [:N] làm mất chữ (vd /grades-detail 5325 ký tự).
LIMIT = 1900
_GAP  = 0.4     # giây nghỉ giữa 2 mẩu — nhẹ tay với API (số mẩu rất nhỏ: 2–3)

async def _send_chunks(send, text):
    """Gửi `text` qua coroutine `send(str)` thành NHIỀU mẩu ≤ LIMIT. True chỉ khi MỌI mẩu đã tới nơi.

    Gửi dở (mẩu đầu tới nơi, mẩu sau hỏng) -> cảnh báo ra log và trả False: người đọc đang thiếu chữ."""
    parts = fmt.chunks(text, LIMIT)
    for i, part in enumerate(parts):
        if i:
            await asyncio.sleep(_GAP)
        try:
            await send(part)
        except Exception as e:                       # noqa: BLE001 — 1 mẩu hỏng không được làm chết bot
            print(f"  gửi lỗi · send error: {e}")
            if i:
                print(t(f"  ⚠️ mới gửi {i}/{len(parts)} mẩu — phần còn lại CHƯA tới nơi.",
                        f"  ⚠️ only {i}/{len(parts)} chunks sent — the rest did NOT arrive."))
            return False
    return True

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
    client = discord.Client(intents=intents)

    # Slash command (/) — danh sách lệnh TỰ GỢI Ý khi gõ '/'. Đăng ký động từ menu_commands().
    # Bọc try/except: nếu phiên bản discord.py không có app_commands thì bot vẫn chạy prefix '!'.
    tree = None
    try:
        tree = discord.app_commands.CommandTree(client)

        def _make(name):
            async def _cmd(interaction, arg: str = None):
                if allow and str(interaction.user.id) != allow:
                    await interaction.response.send_message("⛔ Không có quyền · not allowed.", ephemeral=True)
                    return
                await interaction.response.defer(thinking=True)   # ack <3s; handle() có thể tốn tới 25s
                try:
                    reply = await client.loop.run_in_executor(None, handle, name, arg)
                except SystemExit as e:
                    reply = str(e)
                except Exception as e:                            # noqa: BLE001 — 1 lệnh lỗi không làm chết bot
                    reply = f"Lỗi · error: {e}"
                await _send_chunks(interaction.followup.send, reply)
            return _cmd

        for _n, _d in menu_commands():
            tree.command(name=_n, description=(_d or _n)[:100])(_make(_n))

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
            await _send_chunks(interaction.followup.send, summary)
            if do_restart:
                restart()                                         # thay tiến trình → quay lại với mã mới
        tree.command(name="update",
                     description=t("Cập nhật code + khởi động lại", "Update code + restart")[:100])(_update_cmd)
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

    _started = {"reminder": False, "autoupdate": False}

    @client.event
    async def on_ready():
        if tree is not None:
            try:
                synced = await tree.sync()                        # đăng ký toàn cục (có thể mất tới ~1h để hiện)
                print(f"  /slash: đồng bộ {len(synced)} lệnh (gõ '/' để thấy gợi ý).")
            except Exception as e:                                # noqa: BLE001
                print("  (không sync được /slash — cần mời bot với scope 'applications.commands':", e, ")")
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
        parts = content[len(PREFIX):].split()
        if not parts:
            return
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else None)
        if cmd.strip().lower() == "update":                     # !update — chỉ CHỦ tài khoản
            if not allow or str(message.author.id) != allow:    # chế độ MỞ (allow=None): CHẶN update (tránh self-DoS pull+restart)
                await message.channel.send("⛔ /update chỉ dành cho chủ bot (đặt DISCORD_ALLOWED_USER_ID).")
                return
            if not _update_allowed():                           # checkout dùng chung -> phải bật FAP_ALLOW_UPDATE
                await message.channel.send(_update_off_msg())
                return
            await message.channel.send(t("⏳ Đang cập nhật (git pull + selftest)…", "⏳ Updating (git pull + selftest)…"))
            summary, do_restart = await client.loop.run_in_executor(None, perform_update)
            await _send_chunks(message.channel.send, summary)
            if do_restart:
                restart()                                       # thay tiến trình → quay lại với mã mới
            return
        try:
            # handle() gọi HTTP ĐỒNG BỘ (tới 25s/lệnh) -> chạy trong thread executor,
            # KHÔNG chặn event loop async (giữ heartbeat gateway, bot không bị "lag"/offline).
            reply = await client.loop.run_in_executor(None, handle, cmd, arg)
        except SystemExit as e:
            reply = str(e)
        except Exception as e:                  # noqa: BLE001 — bot không được chết vì 1 lệnh
            reply = f"Lỗi · error: {e}"
        await _send_chunks(message.channel.send, reply)

    client.run(config.DISCORD_BOT_TOKEN)

def main():
    run()

if __name__ == "__main__":
    main()
