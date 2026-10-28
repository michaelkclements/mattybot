"""Roll 1–100 or start a one-minute item leaderboard with /roll."""

from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import logger


MAXIMUM = 100
ROLL_COOLDOWN_SECONDS = 60
LEADERBOARD_DURATION_SECONDS = 60


@dataclass
class LeaderboardEntry:
    """A member's sole scored roll in a leaderboard round."""

    mention: str
    result: int


@dataclass
class LeaderboardRound:
    """An active named leaderboard in a guild."""

    title: str
    channel: discord.abc.Messageable
    ends_at: float
    entries: dict[int, LeaderboardEntry] = field(default_factory=dict)
    completion_task: asyncio.Task[None] | None = None

    def add_entry(self, member_id: int, mention: str, result: int) -> bool:
        """Record a member's only entry, returning whether it was accepted."""
        if member_id in self.entries:
            return False
        self.entries[member_id] = LeaderboardEntry(mention=mention, result=result)
        return True

    def winners(self) -> list[LeaderboardEntry]:
        """Return every entry tied for the highest roll."""
        if not self.entries:
            return []
        highest_result = max(entry.result for entry in self.entries.values())
        return [
            entry for entry in self.entries.values() if entry.result == highest_result
        ]


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
        self._leaderboards: dict[int, LeaderboardRound] = {}

    def cog_unload(self) -> None:
        """Cancel pending result announcements when the cog is unloaded."""
        for leaderboard in self._leaderboards.values():
            if leaderboard.completion_task is not None:
                leaderboard.completion_task.cancel()

    def _leaderboard_remaining(
        self, guild_id: int, now: float | None = None
    ) -> int:
        leaderboard = self._leaderboards.get(guild_id)
        if leaderboard is None:
            return 0
        current_time = time.monotonic() if now is None else now
        return max(0, math.ceil(leaderboard.ends_at - current_time))

    def _start_leaderboard(
        self,
        guild_id: int,
        title: str,
        channel: discord.abc.Messageable,
        now: float | None = None,
    ) -> LeaderboardRound:
        current_time = time.monotonic() if now is None else now
        leaderboard = LeaderboardRound(
            title=title,
            channel=channel,
            ends_at=current_time + LEADERBOARD_DURATION_SECONDS,
        )
        self._leaderboards[guild_id] = leaderboard
        return leaderboard

    def _close_leaderboard(self, guild_id: int, leaderboard: LeaderboardRound) -> None:
        if self._leaderboards.get(guild_id) is leaderboard:
            del self._leaderboards[guild_id]

    @staticmethod
    def _format_winners(winners: list[LeaderboardEntry]) -> str:
        mentions = [winner.mention for winner in winners]
        if len(mentions) == 1:
            return mentions[0]
        if len(mentions) == 2:
            return f"{mentions[0]} and {mentions[1]}"
        return f"{', '.join(mentions[:-1])}, and {mentions[-1]}"

    async def _finish_leaderboard(
        self, guild_id: int, leaderboard: LeaderboardRound
    ) -> None:
        await asyncio.sleep(max(0, leaderboard.ends_at - time.monotonic()))
        if self._leaderboards.get(guild_id) is not leaderboard:
            return

        self._close_leaderboard(guild_id, leaderboard)
        winners = leaderboard.winners()
        if not winners:
            message = (
                f"⏱️ The **{leaderboard.title}** leaderboard is over — "
                "no rolls were recorded."
            )
        else:
            highest_roll = winners[0].result
            winner_label = self._format_winners(winners)
            if len(winners) == 1:
                message = (
                    f"🏆 Congrats, {winner_label} won **{leaderboard.title}** "
                    f"with {highest_roll}"
                )
            else:
                message = (
                    f"🏆 The **{leaderboard.title}** leaderboard is over! "
                    f"It's a tie — congratulations {winner_label} with "
                    f"**{highest_roll}**!"
                )
        try:
            await leaderboard.channel.send(message)
        except discord.HTTPException as exc:
            logger.error(
                "Roll: failed to announce %s leaderboard result: %s",
                leaderboard.title,
                exc,
            )

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

    @app_commands.command(
        name="roll", description="Roll 1–100 or start a one-minute leaderboard."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        item_name="Item being rolled for; starts a one-minute leaderboard."
    )
    async def slash_roll(
        self, interaction: discord.Interaction, item_name: Optional[str] = None
    ) -> None:
        """Roll normally or start/join a one-minute leaderboard."""
        if not isinstance(interaction.user, discord.Member) or interaction.guild_id is None:
            return
        if interaction.channel is None:
            return

        member = interaction.user
        guild_id = interaction.guild_id
        active_leaderboard = self._leaderboards.get(guild_id)
        leaderboard_title = item_name.strip() if item_name else None

        if leaderboard_title and active_leaderboard is not None:
            remaining = self._leaderboard_remaining(guild_id)
            await interaction.response.send_message(
                f"⏳ The **{active_leaderboard.title}** leaderboard is already "
                f"active for **{remaining}s**.",
                ephemeral=True,
            )
            return

        if active_leaderboard is not None and member.id in active_leaderboard.entries:
            await interaction.response.send_message(
                "❌ You have already rolled in this leaderboard.", ephemeral=True
            )
            return
        cooldown_remaining = self._cooldown_remaining(guild_id, member.id)
        if cooldown_remaining:
            await interaction.response.send_message(
                f"⏳ You can roll again in **{cooldown_remaining}s**.", ephemeral=True
            )
            return
        self._start_cooldown(guild_id, member.id)
        result = roll()

        if leaderboard_title:
            active_leaderboard = self._start_leaderboard(
                guild_id, leaderboard_title, interaction.channel
            )
            active_leaderboard.add_entry(member.id, member.mention, result)
            active_leaderboard.completion_task = asyncio.create_task(
                self._finish_leaderboard(guild_id, active_leaderboard)
            )
            await interaction.response.send_message(
                f"A roll for **{leaderboard_title}** has begun — to join in, type `/roll`.\n"
                f"🎲 {member.mention} rolled {result}"
            )
        elif active_leaderboard is not None:
            active_leaderboard.add_entry(member.id, member.mention, result)
            await interaction.response.send_message(
                f"🎲 {member.mention} rolled **{result}**"
            )
        else:
            await interaction.response.send_message(format_roll(result))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roll(bot))
