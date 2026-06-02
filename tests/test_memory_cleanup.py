import errno
import importlib
import os
import tempfile
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("LOCAL_BOT_API_URL", "http://bot-api:8081")
os.environ.setdefault("BOT_API_DIR", "./bot-api/")
os.environ.setdefault("DOWNLOAD_TO_DIR", "./downloads/")
os.environ.setdefault("USER_ID", "1")
os.environ.setdefault("CHAT_ID", "1")

downloader = importlib.import_module("src.cogs.downloader")


class MemoryCleanupTests(unittest.TestCase):
    def tearDown(self):
        downloader._media_group_confirmations.clear()
        downloader._media_group_failed_files.clear()
        downloader._media_group_file_selections.clear()
        downloader._status_cancel_selections.clear()
        try:
            os.unlink(downloader._INTERACTION_STATE_FILE)
        except FileNotFoundError:
            pass

    def test_cross_device_move_uses_low_cache_copy_and_removes_source(self):
        original_replace = downloader.os.replace
        original_drop_file_cache = downloader._drop_file_cache
        drop_calls = []

        def fake_replace(source_path, target_path):
            raise OSError(errno.EXDEV, "cross-device link")

        def fake_drop_file_cache(file_obj, offset=0, length=0):
            drop_calls.append((offset, length))

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "source.bin")
            target_path = os.path.join(temp_dir, "target.bin")
            expected = b"x" * (downloader._LOW_CACHE_COPY_BUFFER_SIZE + 17)
            with open(source_path, "wb") as source:
                source.write(expected)

            downloader.os.replace = fake_replace
            downloader._drop_file_cache = fake_drop_file_cache
            try:
                downloader._move_file_low_cache(source_path, target_path)
            finally:
                downloader.os.replace = original_replace
                downloader._drop_file_cache = original_drop_file_cache

            self.assertFalse(os.path.exists(source_path))
            with open(target_path, "rb") as target:
                self.assertEqual(target.read(), expected)
            self.assertTrue(drop_calls)

    def test_stale_interaction_state_is_pruned(self):
        now = 1000.0
        old = now - downloader._MEDIA_GROUP_SESSION_TTL - 1
        downloader._media_group_confirmations["old"] = {"created_at": old}
        downloader._media_group_confirmations["fresh"] = {"created_at": now}
        downloader._media_group_failed_files["old"] = {"created_at": old}
        downloader._media_group_failed_files["fresh"] = {"created_at": now}
        downloader._status_cancel_selections["old"] = {"created_at": old}
        downloader._status_cancel_selections["fresh"] = {"created_at": now}
        downloader._media_group_file_selections["orphan"] = [True]
        downloader._media_group_file_selections["fresh"] = [True]

        original_now = downloader._monotonic_now
        downloader._monotonic_now = lambda: now
        try:
            downloader._prune_stale_interaction_state()
        finally:
            downloader._monotonic_now = original_now

        self.assertEqual(list(downloader._media_group_confirmations), ["fresh"])
        self.assertEqual(list(downloader._media_group_failed_files), ["fresh"])
        self.assertEqual(list(downloader._status_cancel_selections), ["fresh"])
        self.assertEqual(list(downloader._media_group_file_selections), ["fresh"])

    def test_offloaded_interaction_state_is_loaded_from_disk(self):
        original_state_file = downloader._INTERACTION_STATE_FILE

        with tempfile.TemporaryDirectory() as temp_dir:
            downloader._INTERACTION_STATE_FILE = os.path.join(temp_dir, "interaction_state.json")
            try:
                downloader._set_interaction_state(
                    "media_group_confirmations",
                    "group-1",
                    {
                        "files": [
                            {
                                "file_id": "file-1",
                                "file_name": "file-1.bin",
                                "file_size": 1024,
                                "chat_id": 1,
                                "message_id": 10,
                            }
                        ]
                    },
                )
                downloader._media_group_confirmations["group-1"]["updated_at"] -= (
                    downloader._INTERACTION_STATE_OFFLOAD_AFTER + 1
                )

                downloader._prune_stale_interaction_state()

                self.assertNotIn("group-1", downloader._media_group_confirmations)
                self.assertTrue(os.path.exists(downloader._INTERACTION_STATE_FILE))

                restored = downloader._get_interaction_state(
                    "media_group_confirmations",
                    "group-1",
                )

                self.assertEqual(restored["files"][0]["file_id"], "file-1")
                self.assertIn("group-1", downloader._media_group_confirmations)
                self.assertFalse(os.path.exists(downloader._INTERACTION_STATE_FILE))
            finally:
                downloader._INTERACTION_STATE_FILE = original_state_file


if __name__ == "__main__":
    unittest.main()
