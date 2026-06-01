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

    async def test_get_bot_api_version_falls_back_to_configured_version(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_API_VERSION": "10.1.0"}):
            with patch.object(
                version,
                "_request_bot_api_version_sync",
                side_effect=URLError("unavailable"),
            ):
                result = await version.get_bot_api_version()

        self.assertEqual(result, ("10.1.0", "configured"))


if __name__ == "__main__":
    unittest.main()
