import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.roll import (
    MAXIMUM,
    ROLL_COOLDOWN_SECONDS,
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

    async def invoke(self):
        await Roll.slash_roll.callback(self.cog, self.interaction)

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
        self.assertEqual(cog.get_app_commands()[0].parameters, [])
