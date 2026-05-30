import html
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

general = importlib.import_module("src.cogs.general")


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


if __name__ == "__main__":
    unittest.main()
