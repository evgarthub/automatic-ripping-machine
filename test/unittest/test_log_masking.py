"""Tests for arm.ripper.utils.mask_sensitive_value

Uses fully mocked arm infrastructure to load only the masking function.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "arm_log_masking_test")
os.makedirs(TEST_DIR, exist_ok=True)
_REPO_POSIX = REPO_ROOT.replace("\\", "/")
TEST_DIR_POSIX = TEST_DIR.replace("\\", "/")
_cfg_content = (
    f'INSTALLPATH: "{_REPO_POSIX}/"\n'
    f'DBFILE: "{TEST_DIR_POSIX}/arm.db"\n'
    f'LOGPATH: "{TEST_DIR_POSIX}/logs/"\n'
    f'LOGLEVEL: "ERROR"\n'
    f'ABCDE_CONFIG_FILE: "{_REPO_POSIX}/setup/.abcde.conf"\n'
    f'DATE_FORMAT: "%m-%d-%Y %H:%M:%S"\n'
    f'APPRISE: ""\n'
    f'DISABLE_LOGIN: false\n'
)
_cfg_path = os.path.join(TEST_DIR, "arm.yaml")
with open(_cfg_path, "w", encoding="utf-8") as _f:
    _f.write(_cfg_content)
os.environ["ARM_CONFIG_FILE"] = _cfg_path

for _mod in (
    "pyudev", "fcntl", "discid", "netifaces",
    "bcrypt", "psutil", "requests", "apprise",
):
    try:
        __import__(_mod)
    except Exception:
        sys.modules[_mod] = MagicMock()

sys.path.insert(0, REPO_ROOT)

import arm.config.config  # noqa: F401,E402
from arm.ripper.utils import mask_sensitive_value  # noqa: E402


class TestMaskSensitiveValue(unittest.TestCase):

    def test_mask_standard_sensitive_value(self):
        self.assertEqual(mask_sensitive_value("SECRET_KEY", "supersecret"), "su****et")

    def test_mask_short_value(self):
        self.assertEqual(mask_sensitive_value("my_token", "12345"), "****")

    def test_mask_empty_string(self):
        self.assertEqual(mask_sensitive_value("PASSWORD", ""), "")

    def test_mask_none(self):
        self.assertEqual(mask_sensitive_value("PASSWORD", None), "")

    def test_non_sensitive_key_not_masked(self):
        self.assertEqual(mask_sensitive_value("RIPMETHOD", "mkv"), "mkv")

    def test_apprise_url_masked(self):
        url = "tgram://1234567890:ABCdefGHI-xyz"
        result = mask_sensitive_value("APPRISE", url)
        self.assertNotEqual(result, url)
        self.assertIn("****", result)

    def test_debug_returns_full_value(self):
        self.assertEqual(
            mask_sensitive_value("SECRET_KEY", "supersecret", debug=True),
            "supersecret",
        )

    def test_debug_returns_full_value_for_apprise(self):
        url = "tgram://1234567890:ABCdefGHI-xyz"
        self.assertEqual(mask_sensitive_value("APPRISE", url, debug=True), url)

    def test_key_detection_api_key(self):
        result = mask_sensitive_value("OMDB_API_KEY", "abc123def456")
        self.assertIn("****", result)

    def test_key_detection_access_token(self):
        result = mask_sensitive_value("ACCESS_TOKEN", "abcdef123456")
        self.assertIn("****", result)

    def test_key_detection_appprise(self):
        result = mask_sensitive_value("APPRISE", "tgram://bot:secret@host")
        self.assertIn("****", result)

    def test_key_detection_emby_password(self):
        result = mask_sensitive_value("EMBY_PASSWORD", "p@ssw0rd!")
        self.assertIn("****", result)

    def test_non_sensitive_key_not_masked_hb_preset(self):
        self.assertEqual(
            mask_sensitive_value("HB_PRESET_DVD", "HQ 720p30 Surround"),
            "HQ 720p30 Surround",
        )

    def test_mask_exactly_6_chars(self):
        self.assertEqual(mask_sensitive_value("my_secret", "abcdef"), "ab****ef")

    def test_mask_5_chars(self):
        self.assertEqual(mask_sensitive_value("my_secret", "abcde"), "****")

    def test_url_with_token_param(self):
        url = "https://example.com/api?token=abc123xyz"
        result = mask_sensitive_value("JSON_URL", url)
        self.assertIn("****", result)

    def test_url_with_key_param(self):
        url = "https://example.com/api?key=mysecretkey"
        result = mask_sensitive_value("SOME_URL", url)
        self.assertIn("****", result)


if __name__ == "__main__":
    unittest.main()
