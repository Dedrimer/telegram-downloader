import importlib
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src.models import DownloadFile  # noqa: E402

downloader = importlib.import_module("src.cogs.downloader")


class DownloadProgressTests(unittest.TestCase):
    def test_download_file_tracks_progress_speed_and_eta(self):
        started_at = datetime(2026, 1, 1, 12, 0, 0)
        download_file = DownloadFile(
            "file-id",
            "movie.mkv",
            1024 * 1024,
            _start_datetime=started_at,
        )

        download_file.update_progress(
            512 * 1024,
            now=started_at + timedelta(seconds=2),
        )

        self.assertEqual(download_file.downloaded_bytes, 512 * 1024)
        self.assertEqual(download_file.downloaded_size, "512.00 KB")
        self.assertEqual(download_file.download_progress, "50.00%")
        self.assertEqual(download_file.download_speed, "256.00 KB/s")
        self.assertEqual(download_file.remaining_download_time, "2.00 secs  (0.03 mins)")

        download_file.update_progress(
            128 * 1024,
            now=started_at + timedelta(seconds=3),
        )

        self.assertEqual(download_file.downloaded_bytes, 512 * 1024)

    def test_download_status_update_interval_is_clamped(self):
        self.assertEqual(downloader._clamp_download_status_update_interval(0), 5.0)
        self.assertEqual(downloader._clamp_download_status_update_interval(1), 3.0)
        self.assertEqual(downloader._clamp_download_status_update_interval(10), 10)
        self.assertEqual(downloader._clamp_download_status_update_interval(100), 60.0)

    def test_max_concurrent_downloads_is_clamped(self):
        self.assertEqual(downloader._clamp_max_concurrent_downloads(0), 1)
        self.assertEqual(downloader._clamp_max_concurrent_downloads(2), 2)
        self.assertEqual(downloader._clamp_max_concurrent_downloads(100), 8)

    def test_progress_status_text_includes_detailed_fields(self):
        download_file = DownloadFile("file-id", "movie.mkv", 1024)
        download_file.update_progress(512)

        text = downloader._build_download_status_text(download_file)

        self.assertIn("*Downloaded:*", text)
        self.assertIn("*Progress:* `50.00%`", text)
        self.assertIn("*Speed:*", text)
        self.assertIn("*ETA:*", text)

    def test_queued_download_status_is_visible(self):
        download_file = DownloadFile("file-id", "movie.mkv", 1024)
        download_file.mark_queued()

        text = downloader._build_download_status_text(download_file)

        self.assertIn("*Queued file...*", text)
        self.assertIn("*Status:* `Queued`", text)

    def test_find_download_progress_size_prefers_recent_plausible_file(self):
        old_bot_api_dir = downloader.BOT_API_DIR
        old_token_sub_dir = downloader.TOKEN_SUB_DIR

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                downloader.BOT_API_DIR = temp_dir
                downloader.TOKEN_SUB_DIR = "token"
                token_root = os.path.join(temp_dir, "token")
                os.makedirs(token_root)

                started_at = time.time()
                old_path = os.path.join(token_root, "old.bin")
                with open(old_path, "wb") as old_file:
                    old_file.write(b"x" * 900)
                old_time = started_at - 10
                os.utime(old_path, (old_time, old_time))

                new_path = os.path.join(token_root, "new.bin")
                with open(new_path, "wb") as new_file:
                    new_file.write(b"x" * 512)

                oversized_path = os.path.join(token_root, "oversized.bin")
                with open(oversized_path, "wb") as oversized_file:
                    oversized_file.write(b"x" * 2048)

                download_file = DownloadFile("file-id", "movie.mkv", 1024)
                size, path = downloader._find_download_progress_size(
                    download_file,
                    started_at,
                )

                self.assertEqual(size, 512)
                self.assertEqual(path, new_path)
            finally:
                downloader.BOT_API_DIR = old_bot_api_dir
                downloader.TOKEN_SUB_DIR = old_token_sub_dir


class FakeStatusMessage:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def edit_text(self, text, **kwargs):
        self.calls.append({"text": text, "kwargs": kwargs})
        if self.error:
            raise self.error


class FakeFallbackMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append({"text": text, "kwargs": kwargs})


class DownloadStatusUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_last_update_at = downloader._progress_status_last_update_at
        downloader._progress_status_last_update_at = 0.0

    async def asyncTearDown(self):
        downloader._progress_status_last_update_at = self.old_last_update_at

    async def test_update_download_status_uses_explicit_timeouts(self):
        status_message = FakeStatusMessage()
        fallback_message = FakeFallbackMessage()

        await downloader._update_download_status(
            status_message,
            fallback_message,
            "Downloading",
            timeout=1.5,
        )

        self.assertEqual(len(status_message.calls), 1)
        call_kwargs = status_message.calls[0]["kwargs"]
        self.assertEqual(call_kwargs["read_timeout"], 1.5)
        self.assertEqual(call_kwargs["write_timeout"], 1.5)
        self.assertEqual(call_kwargs["connect_timeout"], 1.5)
        self.assertEqual(call_kwargs["pool_timeout"], 1.5)
        self.assertEqual(fallback_message.replies, [])

    async def test_progress_status_update_is_skipped_when_global_lock_is_busy(self):
        status_message = FakeStatusMessage()
        fallback_message = FakeFallbackMessage()

        await downloader._progress_status_update_lock.acquire()
        try:
            updated = await downloader._try_update_progress_status(
                status_message,
                fallback_message,
                "Progress",
                reply_markup=None,
            )
        finally:
            downloader._progress_status_update_lock.release()

        self.assertFalse(updated)
        self.assertEqual(status_message.calls, [])
        self.assertEqual(fallback_message.replies, [])

    async def test_progress_status_update_does_not_fallback_on_edit_failure(self):
        status_message = FakeStatusMessage(error=TimeoutError("slow edit"))
        fallback_message = FakeFallbackMessage()

        updated = await downloader._try_update_progress_status(
            status_message,
            fallback_message,
            "Progress",
            reply_markup=None,
        )

        self.assertTrue(updated)
        self.assertEqual(len(status_message.calls), 1)
        self.assertEqual(fallback_message.replies, [])


if __name__ == "__main__":
    unittest.main()
