import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.roll import (
    LEADERBOARD_DURATION_SECONDS,
    MAXIMUM,
    ROLL_COOLDOWN_SECONDS,
    LeaderboardRound,
    Roll,
    format_roll,
    roll,
    setup,
)


class RollTests(unittest.TestCase):
    @patch("cogs.roll.random.randint", return_value=42)
    def test_rolls_between_one_and_100(self, randint):
        self.assertEqual(roll(), 42)
        randint.assert_called_once_with(1, MAXIMUM)

    def test_formats_the_result(self):
        self.assertEqual(format_roll(42), "🎲 You rolled **42**.")

    def test_cooldown_lasts_60_seconds(self):
        cog = Roll(bot=None)
        cog._start_cooldown(1, 2, now=100.0)
        self.assertEqual(cog._cooldown_remaining(1, 2, now=100.1), ROLL_COOLDOWN_SECONDS)
        self.assertEqual(cog._cooldown_remaining(1, 2, now=159.1), 1)
        self.assertEqual(cog._cooldown_remaining(1, 2, now=160.0), 0)
        self.assertNotIn((1, 2), cog._cooldowns)

    def test_cooldowns_are_isolated_by_guild_and_member(self):
        cog = Roll(bot=None)
        cog._start_cooldown(1, 2, now=100.0)
        self.assertEqual(cog._cooldown_remaining(1, 3, now=100.0), 0)
        self.assertEqual(cog._cooldown_remaining(2, 2, now=100.0), 0)

    def test_one_entry_per_member_and_highest_roll_wins(self):
        leaderboard = LeaderboardRound("card", None, 160.0)
        self.assertTrue(leaderboard.add_entry(1, "<@1>", 42))
        self.assertFalse(leaderboard.add_entry(1, "<@1>", 99))
        self.assertTrue(leaderboard.add_entry(2, "<@2>", 87))
        self.assertEqual([entry.mention for entry in leaderboard.winners()], ["<@2>"])

    def test_empty_round_has_no_winners(self):
        self.assertEqual(LeaderboardRound("card", None, 160.0).winners(), [])

    def test_closing_old_round_preserves_replacement(self):
        cog = Roll(bot=None)
        original = cog._start_leaderboard(1, "card", None, now=100.0)
        replacement = cog._start_leaderboard(1, "new card", None, now=101.0)
        cog._close_leaderboard(1, original)
        self.assertIs(cog._leaderboards[1], replacement)


class SlashRollTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = Mock()
        self.cog = Roll(self.bot)
        self.interaction = Mock()
        self.interaction.guild_id = 1
        self.interaction.user = Mock(spec=discord.Member)
        self.interaction.user.id = 2
        self.interaction.user.mention = "<@2>"
        self.interaction.response.send_message = AsyncMock()
        self.interaction.channel = AsyncMock()

    async def asyncTearDown(self):
        self.cog.cog_unload()

    async def invoke(self, item_name=None):
        await Roll.slash_roll.callback(self.cog, self.interaction, item_name)

    async def test_ordinary_roll_and_extremes_have_no_special_outcomes(self):
        for result in (1, 42, MAXIMUM):
            with self.subTest(result=result):
                self.cog._cooldowns.clear()
                self.interaction.response.send_message.reset_mock()
                with patch("cogs.roll.roll", return_value=result):
                    await self.invoke()
                self.interaction.response.send_message.assert_awaited_once_with(
                    format_roll(result)
                )
        self.interaction.user.kick.assert_not_called()
        self.bot.get_cog.assert_not_called()
        self.interaction.followup.send.assert_not_called()

    async def test_repeated_roll_is_rejected_ephemerally(self):
        with patch("cogs.roll.roll", return_value=42):
            await self.invoke()
        self.interaction.response.send_message.reset_mock()
        with patch("cogs.roll.roll") as random_roll:
            await self.invoke()
        random_roll.assert_not_called()
        kwargs = self.interaction.response.send_message.await_args.kwargs
        self.assertTrue(kwargs["ephemeral"])

    async def test_starts_named_round_with_initiators_roll(self):
        with patch("cogs.roll.roll", return_value=42):
            await self.invoke("  mew card  ")
        leaderboard = self.cog._leaderboards[1]
        self.assertEqual(leaderboard.title, "mew card")
        self.assertEqual(leaderboard.entries[2].result, 42)
        self.assertIsNotNone(leaderboard.completion_task)
        self.interaction.response.send_message.assert_awaited_once_with(
            "A roll for **mew card** has begun — to join in, type `/roll`.\n"
            "🎲 <@2> rolled 42"
        )

    async def test_joins_active_round_once(self):
        leaderboard = self.cog._start_leaderboard(1, "card", self.interaction.channel)
        with patch("cogs.roll.roll", return_value=87):
            await self.invoke()
        self.assertEqual(leaderboard.entries[2].result, 87)
        self.interaction.response.send_message.reset_mock()
        await self.invoke()
        self.interaction.response.send_message.assert_awaited_once_with(
            "❌ You have already rolled in this leaderboard.", ephemeral=True
        )

    async def test_cannot_start_a_second_round(self):
        original = self.cog._start_leaderboard(1, "card", self.interaction.channel)
        with patch("cogs.roll.roll") as random_roll:
            await self.invoke("another card")
        random_roll.assert_not_called()
        self.assertIs(self.cog._leaderboards[1], original)
        self.assertTrue(self.interaction.response.send_message.await_args.kwargs["ephemeral"])

    async def test_whitespace_item_is_an_ordinary_roll(self):
        with patch("cogs.roll.roll", return_value=42):
            await self.invoke("   ")
        self.assertEqual(self.cog._leaderboards, {})
        self.interaction.response.send_message.assert_awaited_once_with(format_roll(42))

    async def test_dm_does_not_roll(self):
        self.interaction.guild_id = None
        await self.invoke()
        self.interaction.response.send_message.assert_not_awaited()

    async def test_setup_registers_cog_and_command(self):
        bot = AsyncMock()
        await setup(bot)
        cog = bot.add_cog.await_args.args[0]
        self.assertIsInstance(cog, Roll)
        self.assertEqual(cog.get_app_commands()[0].name, "roll")


class LeaderboardCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_announces_winner_and_closes_round(self):
        cog = Roll(bot=None)
        channel = AsyncMock()
        leaderboard = cog._start_leaderboard(1, "mew card", channel, now=100.0)
        leaderboard.add_entry(1, "<@1>", 42)
        leaderboard.add_entry(2, "<@2>", 87)
        with (
            patch("cogs.roll.time.monotonic", return_value=100.0),
            patch("cogs.roll.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            await cog._finish_leaderboard(1, leaderboard)
        sleep.assert_awaited_once_with(LEADERBOARD_DURATION_SECONDS)
        channel.send.assert_awaited_once_with(
            "🏆 Congrats, <@2> won **mew card** with 87"
        )
        self.assertNotIn(1, cog._leaderboards)

    async def test_announces_all_tied_winners(self):
        cog = Roll(bot=None)
        channel = AsyncMock()
        leaderboard = cog._start_leaderboard(1, "card", channel)
        leaderboard.add_entry(1, "<@1>", 100)
        leaderboard.add_entry(2, "<@2>", 100)
        leaderboard.add_entry(3, "<@3>", 99)
        with patch("cogs.roll.asyncio.sleep", new_callable=AsyncMock):
            await cog._finish_leaderboard(1, leaderboard)
        channel.send.assert_awaited_once_with(
            "🏆 The **card** leaderboard is over! "
            "It's a tie — congratulations <@1> and <@2> with **100**!"
        )

    async def test_unloading_cancels_pending_announcement(self):
        cog = Roll(bot=None)
        leaderboard = cog._start_leaderboard(1, "card", AsyncMock())
        leaderboard.completion_task = Mock()
        cog.cog_unload()
        leaderboard.completion_task.cancel.assert_called_once_with()
