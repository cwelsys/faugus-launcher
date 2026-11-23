import tempfile
import unittest
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

    def test_launch_umu_game_id(self):
        self.make_proton("GE", "GE-Proton11-14")
        self.make_proton("Old", "GE-Proton11-12")
        self.assertEqual(core.launch_umu_game_id("anything", "GE"), "umu-default")
        self.assertEqual(core.launch_umu_game_id("anything", "Old"), core.umu_game_id("anything"))

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
        self.assertEqual(self.wm("Old"), "steam_app_" + core.umu_game_id("g")[4:])
        self.assertEqual(self.wm("Old", args="GAMEID=umu-default"), "steam_app_default")
        self.assertEqual(self.wm("Old", args="GAMEID=0"), "steam_app_0")
        self.assertIsNone(self.wm("Steam"))

    def test_default_runner_resolved(self):
        self.make_runners()
        with mock.patch.object(core, "resolve_game_runner", lambda r: "GE" if r == "Default" else r):
            self.assertEqual(self.wm("Default"), "game.exe")


if __name__ == "__main__":
    unittest.main()
