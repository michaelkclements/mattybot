"""
Link converter cog — rewrites x.com links to xcancel.com.

Watches every message in the configured channel. When one contains an x.com
link, the bot replies with the xcancel.com equivalent(s) and suppresses the
original embed so the thread stays clean.
"""

from __future__ import annotations

import re

import discord
from discord.ext import commands

import config
from utils.logger import logger

# Matches http(s)://x.com/... — captures full URL so we can swap the domain
_X_COM_RE = re.compile(
    r"https?://(?:www\.)?x\.com(/[^\s<>\"]*)?",
    re.IGNORECASE,
)


def _convert_links(text: str) -> str | None:
    """Return *text* with all x.com URLs rewritten to xcancel.com, or None if no match."""
    converted, count = _X_COM_RE.subn(
        lambda m: m.group(0).replace("x.com", "xcancel.com", 1),
        text,
    )
    return converted if count else None


class LinkConverter(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Only act on human messages; no channel restriction so it works everywhere
        if message.author.bot:
            return

        converted = _convert_links(message.content)
        if converted is None:
            return

        # Suppress the original x.com embed(s) so we don't get both
        try:
            await message.edit(suppress=True)
        except (discord.Forbidden, discord.HTTPException):
            pass  # we don't have manage_messages — skip silently

        await message.reply(converted, mention_author=False)
        logger.info(
            "LinkConverter: rewrote x.com link(s) in message %d from %s",
            message.id,
            message.author,
        )

    async def cog_load(self) -> None:
        logger.info("LinkConverter loaded — x.com → xcancel.com active")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkConverter(bot))
