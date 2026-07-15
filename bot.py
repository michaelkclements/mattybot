"""
MattyBot — scheduled quote poster + link converter.

Start with: python bot.py

Environment variables (.env):
    DISCORD_TOKEN  — Required. Bot token from the Discord Developer Portal.
    CHANNEL_ID     — Required. ID of the channel to post quotes in.
    GUILD_ID       — Optional. Restrict slash command sync to one guild (instant, dev use).
"""

from __future__ import annotations

import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

import config
from utils.logger import logger

load_dotenv()

_TOKEN:     str | None = os.getenv("DISCORD_TOKEN")
_GUILD_ID:  str | None = os.getenv("GUILD_ID")
_CHANNEL_ID: str | None = os.getenv("CHANNEL_ID")


class MattyBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        # Apply CHANNEL_ID from env into config so cogs pick it up
        if _CHANNEL_ID:
            config.CHANNEL_ID = int(_CHANNEL_ID)

        # Auto-load all cogs
        for cog_path in sorted((Path(__file__).parent / "cogs").glob("*.py")):
            if cog_path.stem.startswith("_"):
                continue
            ext = f"cogs.{cog_path.stem}"
            try:
                await self.load_extension(ext)
                logger.info("Loaded cog: %s", ext)
            except Exception as exc:
                logger.error("Failed to load cog %s: %s", ext, exc)

        # Sync slash commands
        if _GUILD_ID:
            guild = discord.Object(id=int(_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        assert self.user is not None
        logger.info(
            "MattyBot ready — logged in as %s (ID: %d) | discord.py %s",
            self.user, self.user.id, discord.__version__,
        )
        await self.change_presence(activity=None)


def main() -> None:
    if not _TOKEN:
        logger.critical("DISCORD_TOKEN not set. Copy .env.example to .env and add your token.")
        raise SystemExit(1)
    if not _CHANNEL_ID:
        logger.critical("CHANNEL_ID not set. Add it to .env.")
        raise SystemExit(1)

    MattyBot().run(_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
