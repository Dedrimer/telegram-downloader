import os
import unittest
from urllib.error import URLError
from unittest.mock import patch

from src import version


class VersionTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_bot_api_version_uses_reported_version(self):
        with patch.object(
            version, "_request_bot_api_version_sync", return_value="10.1.0"
        ):
            result = await version.get_bot_api_version()

        self.assertEqual(result, ("10.1.0", "api"))

    async def test_get_bot_api_version_is_unknown_when_unavailable(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_API_VERSION": "10.1.0"}):
            with patch.object(
                version,
                "_request_bot_api_version_sync",
                side_effect=URLError("unavailable"),
            ):
                result = await version.get_bot_api_version()

        self.assertEqual(result, ("unknown", "unavailable"))

    async def test_downloader_version_ignores_environment_override(self):
        expected_version = version.VERSION_FILE.read_text(encoding="utf-8").strip()
        with patch.dict(os.environ, {"TELEGRAM_DOWNLOADER_VERSION": "9.9.9"}):
            self.assertEqual(version.get_downloader_version(), expected_version)


if __name__ == "__main__":
    unittest.main()
