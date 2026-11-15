"""
tests/test_app_settings.py - what the app keeps on disk for each user

Covers two ways settings were lost:
  - a Windows scan folder (trailing backslash, network share) breaking the .env file
  - a company list that can't be decrypted looking like an empty list and being saved over
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import PureWindowsPath
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key

import app
import secure_companies


class CleanFolderTests(unittest.TestCase):
    """A folder typed on a Windows PC must survive being stored in .env."""

    def store(self, typed: str) -> str:
        with mock.patch.object(app, "Path", PureWindowsPath), tempfile.TemporaryDirectory() as folder:
            stored = app.clean_folder(typed)
            env_file = os.path.join(folder, ".env")
            open(env_file, "w").close()
            set_key(env_file, "SCAN_FOLDER", stored)
            set_key(env_file, "COMPANIES_KEY", "kept")
            values = dotenv_values(env_file)
        self.assertEqual(values["SCAN_FOLDER"], stored)
        self.assertEqual(values["COMPANIES_KEY"], "kept")     # settings after the folder stay readable
        return stored

    def test_trailing_backslash(self):
        self.assertEqual(self.store("C:\\Scans\\"), "C:/Scans")

    def test_network_share(self):
        self.assertEqual(self.store(r"\\fileserver\scans\inbox"), "//fileserver/scans/inbox")

    def test_quotes_from_copy_as_path(self):
        self.assertEqual(self.store('"C:\\Users\\me\\Desktop"'), "C:/Users/me/Desktop")

    def test_mac_folder(self):
        self.assertEqual(app.clean_folder(" /Users/me/Desktop/ "), "/Users/me/Desktop")

    def test_blank_is_not_a_folder(self):
        self.assertEqual(app.clean_folder("   "), "")


class CompanyListSafetyTests(unittest.TestCase):
    """A list that can't be opened is an error, never an empty list that gets saved over."""

    SAVED = {"companies": [{"name": "Contoso Ltd", "addresses": ["12 Example Street"]}]}

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        paths = mock.patch.multiple(
            secure_companies,
            ENV_FILE=os.path.join(folder.name, ".env"),
            ENC_FILE=os.path.join(folder.name, "companies_reference.enc"),
            JSON_FILE=os.path.join(folder.name, "companies_reference.json"),
        )
        paths.start()
        self.addCleanup(paths.stop)
        environ = mock.patch.dict(os.environ)       # load_dotenv() must not leak into other tests
        environ.start()
        self.addCleanup(environ.stop)
        output = contextlib.redirect_stdout(io.StringIO())   # the module prints key/decryption notes
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        secure_companies.save_encrypted_reference(self.SAVED)

    def saved_bytes(self) -> bytes:
        with open(secure_companies.ENC_FILE, "rb") as f:
            return f.read()

    def use_other_key(self):
        set_key(secure_companies.ENV_FILE, "COMPANIES_KEY", Fernet.generate_key().decode())

    def test_saved_list_opens_again(self):
        self.assertEqual(secure_companies.load_encrypted_reference(strict=True), self.SAVED)

    def test_saving_again_with_the_right_key_works(self):
        secure_companies.save_encrypted_reference({"companies": []})
        self.assertEqual(secure_companies.load_encrypted_reference(strict=True), {"companies": []})

    def test_wrong_key_is_an_error_for_the_app(self):
        self.use_other_key()
        with self.assertRaises(RuntimeError):
            secure_companies.load_encrypted_reference(strict=True)
        with self.assertRaises(RuntimeError):
            app.load_companies()

    def test_wrong_key_does_not_replace_the_list(self):
        before = self.saved_bytes()
        self.use_other_key()
        with self.assertRaises(RuntimeError):
            secure_companies.save_encrypted_reference({"companies": []})
        self.assertEqual(self.saved_bytes(), before)

    def test_missing_key_does_not_replace_the_list(self):
        before = self.saved_bytes()
        open(secure_companies.ENV_FILE, "w").close()
        with self.assertRaises(RuntimeError):
            secure_companies.save_encrypted_reference({"companies": []})
        self.assertEqual(self.saved_bytes(), before)

    def test_command_line_loader_still_returns_an_empty_list(self):
        self.use_other_key()
        self.assertEqual(secure_companies.load_encrypted_reference(), {"companies": []})


class AutostartTests(unittest.TestCase):
    """'Start automatically' writes and removes one per-user file; nothing is really installed here."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = os.path.join(folder.name, "autostart-file")
        path_patch = mock.patch.object(app, "autostart_path", return_value=self.path)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        run_patch = mock.patch.object(app.subprocess, "run")      # no real launchctl
        self.run_mock = run_patch.start()
        self.addCleanup(run_patch.stop)
        self.run_mock.return_value = mock.Mock(returncode=0, stderr="")

    def test_mac_agent_is_written_and_started_at_sign_in(self):
        with mock.patch.object(app.platform, "system", return_value="Darwin"):
            app.set_autostart(True)
            with open(self.path, "rb") as f:
                agent = app.plistlib.load(f)
            self.assertTrue(agent["RunAtLoad"])
            self.assertIn("--no-open", agent["ProgramArguments"])     # must not pop a browser at every sign-in
            self.assertTrue(agent["ProgramArguments"][1].endswith("app.py"))
            self.assertEqual(agent["WorkingDirectory"], app.PROJECT_DIR)
            self.assertTrue(app.autostart_enabled())
            app.set_autostart(False)
        self.assertFalse(os.path.exists(self.path))

    def test_mac_refusal_leaves_nothing_behind(self):
        self.run_mock.return_value = mock.Mock(returncode=5, stderr="denied")
        with mock.patch.object(app.platform, "system", return_value="Darwin"):
            with self.assertRaises(ValueError):
                app.set_autostart(True)
        self.assertFalse(os.path.exists(self.path))

    def test_windows_startup_script_runs_hidden_in_the_app_folder(self):
        with mock.patch.object(app.platform, "system", return_value="Windows"):
            app.set_autostart(True)
            script = open(self.path, encoding="ascii").read()
            self.assertIn(app.PROJECT_DIR, script)
            self.assertIn("app.py", script)
            self.assertIn("--no-open", script)
            self.assertTrue(script.rstrip().endswith(", 0, False"))   # window style 0 = hidden
            app.set_autostart(False)
        self.assertFalse(os.path.exists(self.path))

    def test_unsupported_system_is_refused(self):
        with mock.patch.object(app, "autostart_path", return_value=""):
            with self.assertRaises(ValueError):
                app.set_autostart(True)


if __name__ == "__main__":
    unittest.main()
