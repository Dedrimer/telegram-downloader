import json
import os
import tempfile
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

from src.utils.runtime_settings import RuntimeSettings, RuntimeSettingsStore  # noqa: E402


class RuntimeSettingsTests(unittest.TestCase):
    def test_missing_file_uses_defaults_and_save_writes_json(self):
        defaults = RuntimeSettings(
            single_file_group_enabled=False,
            single_file_group_delay=1.0,
            download_status_update_interval=5.0,
            download_progress_poll_interval=1.0,
            admin_progress_poll_interval=0.5,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "data", "settings.json")
            store = RuntimeSettingsStore(settings_path, defaults)

            self.assertEqual(store.load(), defaults)

            updated = RuntimeSettings(
                single_file_group_enabled=True,
                single_file_group_delay=2.5,
                download_status_update_interval=8.0,
                download_progress_poll_interval=2.0,
                admin_progress_poll_interval=0.25,
            )
            store.save(updated)

            with open(settings_path, encoding="utf-8") as settings_file:
                payload = json.load(settings_file)

            self.assertEqual(
                payload,
                {
                    "download_status_update_interval": 8.0,
                    "download_progress_poll_interval": 2.0,
                    "admin_progress_poll_interval": 0.25,
                    "single_file_group_delay": 2.5,
                    "single_file_group_enabled": True,
                },
            )
            self.assertEqual(RuntimeSettingsStore(settings_path, defaults).load(), updated)

    def test_invalid_values_fall_back_to_defaults(self):
        defaults = RuntimeSettings(
            single_file_group_enabled=False,
            single_file_group_delay=1.0,
            download_status_update_interval=5.0,
            download_progress_poll_interval=1.0,
            admin_progress_poll_interval=0.5,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as settings_file:
                json.dump(
                    {
                        "single_file_group_enabled": "yes",
                        "single_file_group_delay": "invalid",
                        "download_status_update_interval": -1,
                        "download_progress_poll_interval": 0,
                        "admin_progress_poll_interval": "bad",
                    },
                    settings_file,
                )

            settings = RuntimeSettingsStore(settings_path, defaults).load()

            self.assertTrue(settings.single_file_group_enabled)
            self.assertEqual(settings.single_file_group_delay, 1.0)
            self.assertEqual(settings.download_status_update_interval, 5.0)
            self.assertEqual(settings.download_progress_poll_interval, 1.0)
            self.assertEqual(settings.admin_progress_poll_interval, 0.5)


if __name__ == "__main__":
    unittest.main()
