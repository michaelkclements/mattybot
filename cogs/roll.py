"""Roll a random number from 1–100 with /roll."""

from __future__ import annotations

import math
import random
import time

import discord
from discord import app_commands
from discord.ext import commands


MAXIMUM = 100
ROLL_COOLDOWN_SECONDS = 60


def roll() -> int:
    """Return a random integer from 1 through 100."""
    return random.randint(1, MAXIMUM)


def format_roll(result: int) -> str:
    """Format an ordinary roll result."""
    return f"🎲 You rolled **{result}**."


class Roll(commands.Cog):
    """Generate random numbers with /roll, without kicks or immunity."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._cooldowns: dict[tuple[int, int], float] = {}

    def _cooldown_remaining(
        self, guild_id: int, member_id: int, now: float | None = None
    ) -> int:
        current_time = time.monotonic() if now is None else now
        key = (guild_id, member_id)
        next_roll_at = self._cooldowns.get(key)
        if next_roll_at is None or current_time >= next_roll_at:
            self._cooldowns.pop(key, None)
            return 0
        return math.ceil(next_roll_at - current_time)

    def _start_cooldown(
        self, guild_id: int, member_id: int, now: float | None = None
    ) -> None:
        current_time = time.monotonic() if now is None else now
        self._cooldowns[(guild_id, member_id)] = current_time + ROLL_COOLDOWN_SECONDS

    @app_commands.command(name="roll", description="Roll a random number from 1 to 100.")
    @app_commands.guild_only()
    async def slash_roll(self, interaction: discord.Interaction) -> None:
        """Roll once, subject to a per-member, per-guild cooldown."""
        if not isinstance(interaction.user, discord.Member) or interaction.guild_id is None:
            return

        member = interaction.user
        guild_id = interaction.guild_id
        cooldown_remaining = self._cooldown_remaining(guild_id, member.id)
        if cooldown_remaining:
            await interaction.response.send_message(
                f"⏳ You can roll again in **{cooldown_remaining}s**.", ephemeral=True
            )
            return
        self._start_cooldown(guild_id, member.id)
        result = roll()
        await interaction.response.send_message(format_roll(result))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roll(bot))
