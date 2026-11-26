import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from faugus import core, path_manager


class ExeWmClassTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(path_manager, "COMPATIBILITY_DIRS", [Path(self.tmp.name)])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.window_id = mock.patch.object(core, "umu_supports_window_id", return_value=False)
        self.window_id.start()
        self.addCleanup(self.window_id.stop)

    def make_proton(self, name, version_text):
        folder = Path(self.tmp.name) / name
        folder.mkdir(exist_ok=True)
        version = folder / "version"
        if version_text is None:
            version.unlink(missing_ok=True)
        else:
            version.write_text(version_text + "\n")

    def test_supported_versions(self):
        for text, expected in [
            ("1795427215 GE-Proton11-14", True),
            ("GE-Proton11-13", True),
            ("GE-Proton12-1", True),
            ("GE-Proton11-12", False),
            ("GE-Proton10-30", False),
            ("1792352269 dwproton-11.0-15", False),
            ("garbage", False),
            ("", False),
        ]:
            self.make_proton("P", text)
            self.assertEqual(core.proton_names_windows_by_exe("P"), expected, text)

    def test_missing_folder_or_file(self):
        self.assertFalse(core.proton_names_windows_by_exe("Nope"))
        self.make_proton("NoVersion", None)
        self.assertFalse(core.proton_names_windows_by_exe("NoVersion"))
        self.assertFalse(core.proton_names_windows_by_exe(""))

    def wm(self, runner, path="/games/x/Game.exe", args="", gameid="g"):
        return core.game_wm_class({"gameid": gameid, "runner": runner, "launch_arguments": args, "path": path})

    def make_runners(self):
        self.make_proton("GE", "GE-Proton11-14")
        self.make_proton("Old", "GE-Proton11-12")

    def test_supported_uses_exe_name(self):
        self.make_runners()
        self.assertEqual(self.wm("GE"), "game.exe")
        self.assertEqual(self.wm("GE", path="~/games/x/Game.EXE"), "game.exe")
        self.assertEqual(self.wm("GE", args="GAMEID=umu-default"), "game.exe")
        self.assertEqual(self.wm("GE", args="GAMEID=0"), "game.exe")

    def test_supported_non_exe_path_has_no_class(self):
        self.make_runners()
        for path in ["/games/x/setup.msi", "/games/x/run.bat", "/games/x/Game.lnk", ""]:
            self.assertIsNone(self.wm("GE", path=path), path)

    def test_explicit_steam_id_kept(self):
        self.make_runners()
        self.assertEqual(self.wm("GE", args="GAMEID=umu-12345"), "steam_app_12345")

    def test_override(self):
        self.make_runners()
        self.assertEqual(self.wm("GE", args="X=1 FAUGUS_WM_CLASS=other.exe"), "other.exe")
        self.assertEqual(self.wm("Old", args="FAUGUS_WM_CLASS=other.exe"), "other.exe")

    def test_unsupported_unchanged(self):
        self.make_runners()
        self.assertEqual(self.wm("Old"), "steam_app_default")
        self.assertEqual(self.wm("Old", args="GAMEID=umu-12345"), "steam_app_12345")
        self.assertEqual(self.wm("Old", args="GAMEID=umu-default"), "steam_app_default")
        self.assertEqual(self.wm("Old", args="GAMEID=0"), "steam_app_0")
        self.assertIsNone(self.wm("Steam"))

    def test_default_runner_resolved(self):
        self.make_runners()
        with mock.patch.object(core, "resolve_game_runner", lambda r: "GE" if r == "Default" else r):
            self.assertEqual(self.wm("Default"), "game.exe")

    def test_window_id_support_names_every_runner_by_window_id(self):
        self.make_runners()
        expected = "steam_app_" + core.umu_window_id("g")
        with mock.patch.object(core, "umu_supports_window_id", return_value=True):
            self.assertEqual(self.wm("GE"), expected)
            self.assertEqual(self.wm("Old"), expected)
            self.assertEqual(self.wm("GE", args="GAMEID=umu-12345"), expected)
            self.assertEqual(self.wm("GE", args="FAUGUS_WM_CLASS=other.exe"), "other.exe")
            self.assertIsNone(self.wm("Steam"))

    def test_umu_window_id_detection(self):
        self.window_id.stop()
        root = Path(self.tmp.name)
        for name, source, expected in [
            ("new", b'os.environ.get("UMU_WINDOW_ID", "")', True),
            ("old", b'os.environ.get("GAMEID", "")', False),
        ]:
            umu_run = root / name
            with zipfile.ZipFile(umu_run, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("umu/umu_run.py", source)
            self.assertEqual(core.umu_supports_window_id(umu_run), expected, name)
        script = root / "script"
        script.write_bytes(b"#!/bin/sh\nUMU_WINDOW_ID=1\n")
        self.assertTrue(core.umu_supports_window_id(script))
        self.assertFalse(core.umu_supports_window_id(root / "missing"))
        self.window_id.start()

    def write_shortcut(self, body):
        apps = Path(self.tmp.name) / "applications"
        apps.mkdir(exist_ok=True)
        shortcut = apps / "g.desktop"
        shortcut.write_text(body)
        return apps, shortcut

    def refresh(self, apps, runner="GE", path="/games/x/Game.exe"):
        game = {"gameid": "g", "runner": runner, "launch_arguments": "", "path": path}
        core.refresh_shortcut_wm_class(game, [apps])

    def test_refresh_rewrites_stale_class(self):
        self.make_runners()
        apps, shortcut = self.write_shortcut("[Desktop Entry]\nName=G\nStartupWMClass=steam_app_faugusdeadbeef\nIcon=x\n")
        self.refresh(apps)
        self.assertEqual(shortcut.read_text(), "[Desktop Entry]\nName=G\nStartupWMClass=game.exe\nIcon=x\n")

    def test_refresh_adds_missing_class(self):
        self.make_runners()
        apps, shortcut = self.write_shortcut("[Desktop Entry]\nName=G\n")
        self.refresh(apps)
        self.assertEqual(shortcut.read_text(), "[Desktop Entry]\nName=G\nStartupWMClass=game.exe\n")

    def test_refresh_removes_class_when_unknown(self):
        self.make_runners()
        apps, shortcut = self.write_shortcut("[Desktop Entry]\nName=G\nStartupWMClass=steam_app_0\n")
        self.refresh(apps, path="/games/x/setup.msi")
        self.assertEqual(shortcut.read_text(), "[Desktop Entry]\nName=G\n")

    def test_refresh_leaves_unsupported_and_missing_alone(self):
        self.make_runners()
        body = "[Desktop Entry]\nStartupWMClass=steam_app_default\n"
        apps, shortcut = self.write_shortcut(body)
        self.refresh(apps, runner="Old")
        self.assertEqual(shortcut.read_text(), body)
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        core.refresh_shortcut_wm_class({"gameid": "g", "runner": "GE", "path": "/games/x/Game.exe"}, [empty, None])
        self.assertEqual(list(empty.iterdir()), [])

    def test_unreadable_version_is_unsupported(self):
        folder = Path(self.tmp.name) / "Bad"
        folder.mkdir()
        (folder / "version").write_bytes(b"\xff\xfeGE-Proton11-14")
        self.assertFalse(core.proton_names_windows_by_exe("Bad"))

    def test_launch_command_agrees_with_shortcut(self):
        from faugus import runner
        self.make_runners()
        resolve = lambda r: "GE" if r == "Default" else r
        cases = [
            ("Default", "", "game.exe"),
            ("GE", "", "game.exe"),
            ("GE", "GAMEID=umu-12345", "steam_app_12345"),
            ("Old", "", "steam_app_default"),
        ]
        with mock.patch.object(core, "resolve_game_runner", resolve), mock.patch.object(runner, "resolve_game_runner", resolve):
            for runner_name, args, expected_class in cases:
                game = {"gameid": "g", "runner": runner_name, "launch_arguments": args, "path": "/games/x/Game.exe", "prefix": "/p"}
                words = runner.build_launch_command(game).split()
                self.assertIn("UMU_WINDOW_ID=" + core.umu_window_id("g"), words, runner_name)
                self.assertFalse(any(w.startswith("GAMEID=") for w in words if w != args), runner_name)
                self.assertEqual(core.game_wm_class(game), expected_class, runner_name)


if __name__ == "__main__":
    unittest.main()
