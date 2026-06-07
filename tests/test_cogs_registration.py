import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src.cogs import general_commands  # noqa: E402


class CogsRegistrationTests(unittest.TestCase):
    def test_language_command_is_registered(self):
        commands = {
            command
            for handler in general_commands
            for command in getattr(handler, "commands", set())
        }

        self.assertIn("language", commands)


if __name__ == "__main__":
    unittest.main()
