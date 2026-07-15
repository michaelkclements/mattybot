"""
Quotes cog — posts quotes when the chat is busy.

Busy chat (10+ messages in 10 minutes) → random chance to drop a quote
after each message. 50/50 whether it replies to the sender or posts standalone.
"""

from __future__ import annotations

import random
import time
from collections import deque

import discord
from discord.ext import commands

import config
from utils.logger import logger


class Quotes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._message_times: deque[float] = deque()
        self._last_quote_text: str | None = None  # prevents back-to-back repeats

    def _prune_window(self) -> None:
        cutoff = time.monotonic() - config.MESSAGE_WINDOW
        while self._message_times and self._message_times[0] < cutoff:
            self._message_times.popleft()

    def _is_busy(self) -> bool:
        self._prune_window()
        return len(self._message_times) >= config.BUSY_THRESHOLD

    def _pick_quote(self, pool: list[str]) -> str:
        """Pick a random quote, avoiding the last one sent."""
        choices = [q for q in pool if q != self._last_quote_text] or pool
        return random.choice(choices)

    async def _post_quote(
        self,
        channel: discord.abc.Messageable,
        reply_to: discord.Message | None = None,
    ) -> None:
        all_quotes = config.REPLY_QUOTES + config.STANDALONE_QUOTES
        if not all_quotes:
            logger.warning("Quotes: no quotes configured.")
            return

        if reply_to and config.REPLY_QUOTES:
            quote = self._pick_quote(config.REPLY_QUOTES)
            await reply_to.reply(quote)
        else:
            quote = self._pick_quote(config.STANDALONE_QUOTES or all_quotes)
            await channel.send(quote)

        self._last_quote_text = quote
        logger.info("Quotes: posted%s", " (reply)" if reply_to else "")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != config.CHANNEL_ID:
            return
        if message.author.bot:
            return

        self._message_times.append(time.monotonic())
        self._prune_window()

        if self._is_busy() and random.random() < config.BUSY_QUOTE_CHANCE:
            reply = message if random.random() < 0.5 else None
            await self._post_quote(message.channel, reply_to=reply)

    async def cog_load(self) -> None:
        logger.info(
            "Quotes loaded — channel: %d | busy: %d msgs/%ds | chance: %.0f%%",
            config.CHANNEL_ID,
            config.BUSY_THRESHOLD,
            config.MESSAGE_WINDOW,
            config.BUSY_QUOTE_CHANCE * 100,
        )
        if config.CHANNEL_ID == 0:
            logger.error("Quotes: CHANNEL_ID is 0 — set it in your .env!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Quotes(bot))
