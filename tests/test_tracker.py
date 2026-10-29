import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main


class TrackerTests(unittest.TestCase):
    def test_profile_normalization_handles_missing_optional_fields(self):
        snapshot = main.normalize_profile({"name": "Uther", "realm": {"name": "Silvermoon"}})
        self.assertEqual(snapshot["name"], "Uther")
        self.assertEqual(snapshot["realm"], "Silvermoon")
        self.assertIsNone(snapshot["item_level"])

    def test_demo_refresh_is_labeled_and_persisted(self):
        with tempfile.TemporaryDirectory(dir=main.ROOT) as folder:
            database = Path(folder) / "test.sqlite3"
            with patch.object(main, "DATA_DIR", Path(folder)), patch.object(main, "DATABASE", database), patch.object(main, "DEMO_MODE", True):
                main.initialize_database()
                success, _ = main.refresh()
                state = main.current_state()
        self.assertTrue(success)
        self.assertEqual(state["mode"], "demo")
        self.assertEqual(state["latest"]["name"], "Uther")
        self.assertEqual(state["latest"]["is_demo"], 1)
        self.assertEqual(len(state["history"]), 1)

    def test_demo_snapshot_is_hidden_when_live_mode_starts(self):
        with tempfile.TemporaryDirectory(dir=main.ROOT) as folder:
            database = Path(folder) / "test.sqlite3"
            with patch.object(main, "DATA_DIR", Path(folder)), patch.object(main, "DATABASE", database), patch.object(main, "DEMO_MODE", True):
                main.initialize_database()
                main.refresh()
            with patch.object(main, "DATABASE", database), patch.object(main, "DEMO_MODE", False):
                state = main.current_state()
        self.assertIsNone(state["latest"])
        self.assertEqual(state["history"], [])

    def test_blizzard_request_uses_eu_character_profile(self):
        responses = [
            io.BytesIO(b'{"access_token":"test-token"}'),
            io.BytesIO(b'{"name":"Uther"}'),
        ]
        with patch.dict(os.environ, {"BLIZZARD_CLIENT_ID": "id", "BLIZZARD_CLIENT_SECRET": "secret"}), patch.object(main.request, "urlopen", side_effect=responses) as urlopen:
            profile = main.fetch_profile()
        self.assertEqual(profile["name"], "Uther")
        token_request = urlopen.call_args_list[0].args[0]
        profile_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(token_request.full_url, "https://eu.battle.net/oauth/token")
        self.assertIn("/profile/wow/character/silvermoon/uther", profile_request.full_url)
        self.assertIn("namespace=profile-eu", profile_request.full_url)
        self.assertEqual(profile_request.get_header("Authorization"), "Bearer test-token")


if __name__ == "__main__":
    unittest.main()
