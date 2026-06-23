#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discordbot.py — Bot Discord TƯƠNG TÁC (discord.py, optional extra [bot]).

    pip install -e ".[bot]"
    fap discord-bot          # chạy nền, trả lời lệnh prefix `!` (vd !today, !grades)

Cần: DISCORD_BOT_TOKEN (Developer Portal → Bot → Token) trong .env, và bật quyền
"MESSAGE CONTENT INTENT" cho bot. Bảo mật: nếu đặt DISCORD_ALLOWED_USER_ID thì CHỈ trả lời
user đó (khuyến nghị mạnh — tránh lộ dữ liệu). Prefix mặc định `!`. Xem docs/13-notify.md.
"""
from .. import config
from .bot_core import handle, menu_commands

PREFIX = "!"

def run():
    try:
        import discord
    except ImportError:
        raise SystemExit('Thiếu discord.py. Cài: pip install -e ".[bot]"  (cần Python ≥ 3.8)')
    if not config.DISCORD_BOT_TOKEN:
        raise SystemExit("Thiếu DISCORD_BOT_TOKEN trong .env (Developer Portal → Bot → Reset Token).")
    allow = str(config.DISCORD_ALLOWED_USER_ID) if config.DISCORD_ALLOWED_USER_ID else None
    if not allow:
        import os
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
                await interaction.followup.send(reply[:1900])
            return _cmd

        for _n, _d in menu_commands():
            tree.command(name=_n, description=(_d or _n)[:100])(_make(_n))
    except Exception as e:                                        # noqa: BLE001
        print("  (slash command không khả dụng, chỉ dùng prefix '!':", e, ")")
        tree = None

    @client.event
    async def on_ready():
        if tree is not None:
            try:
                synced = await tree.sync()                        # đăng ký toàn cục (có thể mất tới ~1h để hiện)
                print(f"  /slash: đồng bộ {len(synced)} lệnh (gõ '/' để thấy gợi ý).")
            except Exception as e:                                # noqa: BLE001
                print("  (không sync được /slash — cần mời bot với scope 'applications.commands':", e, ")")
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
        try:
            # handle() gọi HTTP ĐỒNG BỘ (tới 25s/lệnh) -> chạy trong thread executor,
            # KHÔNG chặn event loop async (giữ heartbeat gateway, bot không bị "lag"/offline).
            reply = await client.loop.run_in_executor(None, handle, cmd, arg)
        except SystemExit as e:
            reply = str(e)
        except Exception as e:                  # noqa: BLE001 — bot không được chết vì 1 lệnh
            reply = f"Lỗi · error: {e}"
        await message.channel.send(reply[:1900])

    client.run(config.DISCORD_BOT_TOKEN)

def main():
    run()

if __name__ == "__main__":
    main()
