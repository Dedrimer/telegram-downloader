import asyncio
import importlib
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

downloader = importlib.import_module("src.cogs.downloader")


class FakeMessage:
    def __init__(self, message_id: int, file_id: str):
        self.chat_id = 1
        self.message_id = message_id
        self.media_group_id = None
        self.document = SimpleNamespace(
            file_id=file_id,
            file_name=f"{file_id}.bin",
            file_size=1024,
            mime_type="application/octet-stream",
        )
        self.video = None
        self.audio = None


def make_update(message_id: int, file_id: str):
    return SimpleNamespace(message=FakeMessage(message_id, file_id))


class SingleFileGroupingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await self._reset_grouping_state()

    async def asyncTearDown(self):
        await self._reset_grouping_state()

    async def _reset_grouping_state(self):
        timers = list(downloader._single_file_group_timers.values())
        downloader._single_file_group_timers.clear()
        downloader._pending_single_file_groups.clear()
        downloader._single_file_grouping_enabled = False
        downloader._single_file_grouping_delay = 1.0

        for timer in timers:
            timer.cancel()
        if timers:
            await asyncio.gather(*timers, return_exceptions=True)

    async def test_consecutive_single_files_reset_timer_and_share_one_group(self):
        calls = []

        async def fake_handle_media_group(files_info, context, media_group_id=None):
            calls.append((files_info, context, media_group_id))

        original_handler = downloader._handle_media_group_download
        downloader._handle_media_group_download = fake_handle_media_group
        downloader._single_file_grouping_enabled = True
        downloader._single_file_grouping_delay = 0.05
        context = SimpleNamespace(bot=SimpleNamespace())

        try:
            self.assertTrue(
                await downloader._queue_single_file_for_grouping(
                    make_update(10, "file-a"),
                    context,
                )
            )
            await asyncio.sleep(0.03)
            self.assertTrue(
                await downloader._queue_single_file_for_grouping(
                    make_update(11, "file-b"),
                    context,
                )
            )
            await asyncio.sleep(0.03)
            self.assertEqual(calls, [])

            await asyncio.sleep(0.04)

            self.assertEqual(len(calls), 1)
            files_info, called_context, media_group_id = calls[0]
            self.assertIs(called_context, context)
            self.assertEqual([info[0] for info, _ in files_info], ["file-a", "file-b"])
            self.assertEqual(media_group_id, "single-1-10-11")
        finally:
            downloader._handle_media_group_download = original_handler

    async def test_disabled_grouping_does_not_queue_single_file(self):
        context = SimpleNamespace(bot=SimpleNamespace())

        self.assertFalse(
            await downloader._queue_single_file_for_grouping(
                make_update(10, "file-a"),
                context,
            )
        )
        self.assertEqual(downloader._pending_single_file_groups, {})
        self.assertEqual(downloader._single_file_group_timers, {})


if __name__ == "__main__":
    unittest.main()
