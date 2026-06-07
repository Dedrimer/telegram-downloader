import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src.utils.i18n import t  # noqa: E402


class I18nTests(unittest.TestCase):
    def test_translations_decode_newlines(self):
        text = t("download.title") + t("download.status_downloaded_files", completed_files=0, total_files=1)

        self.assertIn("\n", text)
        self.assertNotIn("\\n", text)


if __name__ == "__main__":
    unittest.main()
