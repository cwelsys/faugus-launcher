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


if __name__ == "__main__":
    unittest.main()
