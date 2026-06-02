import html
import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

general = importlib.import_module("src.cogs.general")
version = importlib.import_module("src.version")


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, parse_mode=None):
        self.replies.append({"text": text, "parse_mode": parse_mode})


class GeneralHelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_help_command_uses_html_for_underscore_command(self):
        message = FakeMessage()
        update = SimpleNamespace(message=message)

        await general.help_command.callback(update, SimpleNamespace())

        self.assertEqual(len(message.replies), 1)
        reply = message.replies[0]
        self.assertEqual(reply["parse_mode"], "HTML")
        self.assertIn("<code>/single_group</code>", reply["text"])
        self.assertIn(
            f"<code>{html.escape(general.DOWNLOAD_TO_DIR)}</code>",
            reply["text"],
        )

    async def test_info_command_reports_container_versions(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=42),
            effective_chat=SimpleNamespace(id=-100),
            message=message,
        )
        runtime_info = version.RuntimeInfo(
            downloader_version="0.2.1",
            bot_api_version="10.1.0",
            bot_api_version_source="api",
        )

        with patch.object(
            general, "get_runtime_info", AsyncMock(return_value=runtime_info)
        ):
            await general.info.callback(update, SimpleNamespace())

        self.assertEqual(len(message.replies), 1)
        reply = message.replies[0]
        self.assertEqual(reply["parse_mode"], "HTML")
        self.assertIn("<b>User ID</b>: <code>42</code>", reply["text"])
        self.assertIn("<b>Chat ID</b>: <code>-100</code>", reply["text"])
        self.assertIn(
            "<code>telegram-downloader</code>: <code>0.2.1</code>", reply["text"]
        )
        self.assertIn(
            "<code>telegram-bot-api</code>: <code>10.1.0</code>", reply["text"]
        )


if __name__ == "__main__":
    unittest.main()
