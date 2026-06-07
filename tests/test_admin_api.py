import os
import unittest
from unittest.mock import patch

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src import admin_api  # noqa: E402
from src.models import DownloadFile, downloading_files  # noqa: E402


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.old_downloading_files = dict(downloading_files)
        downloading_files.clear()

    def tearDown(self):
        downloading_files.clear()
        downloading_files.update(self.old_downloading_files)

    def test_downloads_payload_splits_active_and_queued_counts(self):
        active = DownloadFile("active-id", "active.bin", 100)
        active.update_progress(25)
        queued = DownloadFile("queued-id", "queued.bin", 200)
        queued.mark_queued()
        downloading_files["active-id"] = active
        downloading_files["queued-id"] = queued

        payload = admin_api._downloads_payload()

        self.assertEqual(payload["summary"]["total"], 2)
        self.assertEqual(payload["summary"]["downloading"], 1)
        self.assertEqual(payload["summary"]["queued"], 1)
        self.assertEqual(payload["items"][0]["progress_percent"], 25.0)

    def test_overview_payload_contains_expected_top_level_sections(self):
        with patch.object(admin_api, "_bot_api_status", return_value={"online": False}):
            payload = admin_api._overview_payload()

        self.assertIn("downloads", payload)
        self.assertIn("system", payload)
        self.assertIn("bot", payload)
        self.assertIn("resources", payload["system"])

    def test_authorization_accepts_empty_token(self):
        handler = object.__new__(admin_api.AdminApiHandler)
        handler.headers = {}

        with patch.object(admin_api.env, "ADMIN_API_TOKEN", ""):
            self.assertTrue(handler._authorized())

    def test_authorization_requires_matching_token(self):
        handler = object.__new__(admin_api.AdminApiHandler)
        handler.headers = {"X-Admin-Token": "secret"}

        with patch.object(admin_api.env, "ADMIN_API_TOKEN", "secret"):
            self.assertTrue(handler._authorized())

        handler.headers = {"X-Admin-Token": "wrong"}
        with patch.object(admin_api.env, "ADMIN_API_TOKEN", "secret"):
            self.assertFalse(handler._authorized())

    def test_admin_heartbeat_controls_sampler_state(self):
        stopped = admin_api._set_admin_heartbeat(False)
        self.assertFalse(stopped["active"])

        started = admin_api._set_admin_heartbeat(True, ttl=5)
        self.assertTrue(started["enabled"])
        self.assertTrue(started["active"])

        stopped = admin_api._set_admin_heartbeat(False)
        self.assertFalse(stopped["enabled"])
        self.assertFalse(stopped["active"])


if __name__ == "__main__":
    unittest.main()
