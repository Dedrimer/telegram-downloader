import asyncio
import importlib
import os
import unittest
from unittest.mock import patch

from telegram.error import BadRequest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src.models import DownloadFile  # noqa: E402

get_file_module = importlib.import_module("src.utils.get_file")


class FakeGetFileBot:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def get_file(self, file_id, read_timeout=None):
        self.calls += 1
        raise self.error


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class CancelFileDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_get_file_response_stops_retries(self):
        bot = FakeGetFileBot(BadRequest("file download was cancelled"))
        download_file = DownloadFile("file-id", "movie.mkv", 1024)

        with self.assertRaises(asyncio.CancelledError):
            await get_file_module.get_file(bot, download_file)

        self.assertEqual(bot.calls, 1)

    async def test_cancel_requested_stops_network_errors(self):
        bot = FakeGetFileBot(BadRequest("temporary network failure"))
        download_file = DownloadFile("file-id", "movie.mkv", 1024)
        download_file.request_cancel()

        with self.assertRaises(asyncio.CancelledError):
            await get_file_module.get_file(bot, download_file)

        self.assertEqual(bot.calls, 0)
        self.assertEqual(download_file.status, "Cancelling")


class CancelFileDownloadHttpTests(unittest.TestCase):
    def test_cancel_file_download_posts_form_encoded_file_id(self):
        response = FakeResponse(b'{"ok":true,"result":true}')

        with patch.object(get_file_module, "urlopen", return_value=response) as urlopen:
            result = get_file_module._cancel_file_download_sync("file id/1")

        request = urlopen.call_args.args[0]
        self.assertTrue(result)
        self.assertEqual(
            request.full_url,
            "http://bot-api:8081/bot123:ABC/cancelFileDownload",
        )
        self.assertEqual(request.data, b"file_id=file+id%2F1")
        self.assertEqual(
            urlopen.call_args.kwargs["timeout"],
            get_file_module.CANCEL_FILE_DOWNLOAD_TIMEOUT,
        )

    def test_cancel_file_download_returns_false_when_api_result_is_false(self):
        response = FakeResponse(b'{"ok":true,"result":false}')

        with patch.object(get_file_module, "urlopen", return_value=response):
            result = get_file_module._cancel_file_download_sync("file-id")

        self.assertFalse(result)

    def test_get_file_download_progress_posts_form_encoded_file_id(self):
        response = FakeResponse(
            b'{"ok":true,"result":{"downloaded_size":512,"is_downloading_active":true}}'
        )

        with patch.object(get_file_module, "urlopen", return_value=response) as urlopen:
            result = get_file_module._get_file_download_progress_sync("file id/1")

        request = urlopen.call_args.args[0]
        self.assertEqual(result["downloaded_size"], 512)
        self.assertEqual(
            request.full_url,
            "http://bot-api:8081/bot123:ABC/getFileDownloadProgress",
        )
        self.assertEqual(request.data, b"file_id=file+id%2F1")
        self.assertEqual(
            urlopen.call_args.kwargs["timeout"],
            get_file_module.GET_FILE_DOWNLOAD_PROGRESS_TIMEOUT,
        )


if __name__ == "__main__":
    unittest.main()
