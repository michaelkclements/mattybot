import unittest
from unittest.mock import AsyncMock, patch

import discord

from bot import MattyBot


class CommandSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_guild_mode_removes_global_copy_but_keeps_guild_roll(self):
        with patch("bot._GUILD_ID", "123"), patch("bot._CHANNEL_ID", None):
            async with MattyBot() as bot:
                bot.tree.sync = AsyncMock(return_value=[])
                await bot.setup_hook()

                guild = discord.Object(id=123)
                self.assertEqual(bot.tree.sync.await_count, 2)
                first_call, second_call = bot.tree.sync.await_args_list
                self.assertEqual(first_call.kwargs["guild"].id, 123)
                self.assertEqual(second_call.kwargs, {})
                self.assertIsNone(bot.tree.get_command("roll"))
                command = bot.tree.get_command("roll", guild=guild)
                self.assertIsNotNone(command)
                self.assertEqual(command.parameters, [])

    async def test_global_mode_keeps_global_roll(self):
        with patch("bot._GUILD_ID", None), patch("bot._CHANNEL_ID", None):
            async with MattyBot() as bot:
                bot.tree.sync = AsyncMock(return_value=[])
                await bot.setup_hook()

                bot.tree.sync.assert_awaited_once_with()
                command = bot.tree.get_command("roll")
                self.assertIsNotNone(command)
                self.assertEqual(command.parameters, [])

    async def test_failed_guild_sync_does_not_remove_global_commands(self):
        with patch("bot._GUILD_ID", "123"), patch("bot._CHANNEL_ID", None):
            async with MattyBot() as bot:
                bot.tree.sync = AsyncMock(side_effect=RuntimeError("Sync failed"))
                with self.assertRaisesRegex(RuntimeError, "Sync failed"):
                    await bot.setup_hook()

                self.assertEqual(bot.tree.sync.await_count, 1)
                self.assertIsNotNone(bot.tree.get_command("roll"))
