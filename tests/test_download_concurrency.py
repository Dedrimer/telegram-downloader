import asyncio
import importlib
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")
os.environ.setdefault("MAX_CONCURRENT_DOWNLOADS", "1")

downloader = importlib.import_module("src.cogs.downloader")


class DownloadConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_file_downloads_are_limited_by_global_semaphore(self):
        old_bot_api_dir = downloader.BOT_API_DIR
        old_download_to_dir = downloader.DOWNLOAD_TO_DIR
        old_token_sub_dir = downloader.TOKEN_SUB_DIR
        old_get_file = downloader.get_file
        old_check_file_exists = downloader.check_file_exists
        old_update_download_status = downloader._update_download_status
        old_download_semaphore = downloader._download_semaphore
        old_max_concurrent_downloads = downloader._max_concurrent_downloads

        active_downloads = 0
        max_active_downloads = 0

        async def fake_get_file(bot, download_file):
            nonlocal active_downloads, max_active_downloads
            active_downloads += 1
            max_active_downloads = max(max_active_downloads, active_downloads)
            try:
                await asyncio.sleep(0.05)
                relative_path = f"{download_file.file_id}.bin"
                source_path = os.path.join(
                    downloader.BOT_API_DIR,
                    downloader.TOKEN_SUB_DIR,
                    relative_path,
                )
                with open(source_path, "wb") as source_file:
                    source_file.write(b"data")
                return SimpleNamespace(file_path=relative_path)
            finally:
                active_downloads -= 1

        async def fake_update_download_status(*args, **kwargs):
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            api_dir = os.path.join(temp_dir, "api") + os.sep
            output_dir = os.path.join(temp_dir, "downloads") + os.sep
            os.makedirs(os.path.join(api_dir, "token"))
            os.makedirs(output_dir)

            downloader.BOT_API_DIR = api_dir
            downloader.DOWNLOAD_TO_DIR = output_dir
            downloader.TOKEN_SUB_DIR = "token"
            downloader.get_file = fake_get_file
            downloader.check_file_exists = lambda *args, **kwargs: True
            downloader._update_download_status = fake_update_download_status
            downloader._max_concurrent_downloads = 1
            downloader._download_semaphore = asyncio.Semaphore(1)
            downloader.downloading_files.clear()
            downloader._download_tasks.clear()
            downloader._download_cancel_tokens.clear()

            try:
                context = SimpleNamespace(bot=SimpleNamespace())
                message = SimpleNamespace()
                results = await asyncio.gather(
                    downloader._download_single_file(
                        "file-a",
                        "file-a.out",
                        4,
                        message,
                        context,
                    ),
                    downloader._download_single_file(
                        "file-b",
                        "file-b.out",
                        4,
                        message,
                        context,
                    ),
                )
            finally:
                downloader.BOT_API_DIR = old_bot_api_dir
                downloader.DOWNLOAD_TO_DIR = old_download_to_dir
                downloader.TOKEN_SUB_DIR = old_token_sub_dir
                downloader.get_file = old_get_file
                downloader.check_file_exists = old_check_file_exists
                downloader._update_download_status = old_update_download_status
                downloader._download_semaphore = old_download_semaphore
                downloader._max_concurrent_downloads = old_max_concurrent_downloads
                downloader.downloading_files.clear()
                downloader._download_tasks.clear()
                downloader._download_cancel_tokens.clear()

        self.assertEqual(results, [True, True])
        self.assertEqual(max_active_downloads, 1)
