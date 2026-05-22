import unittest
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
ADDON_DIRS = [
    ROOT_DIR / "openpool",
    ROOT_DIR / "ecotracker_meter_bridge",
]


class RepositoryTest(unittest.TestCase):
    def test_repository_metadata(self):
        metadata = yaml.safe_load((ROOT_DIR / "repository.yaml").read_text())

        self.assertEqual(metadata["name"], "Andre's HA-Addons")
        self.assertEqual(metadata["url"], "https://github.com/cococheaf/ha-addons")

    def test_addon_configs_are_valid_yaml(self):
        for addon_dir in ADDON_DIRS:
            with self.subTest(addon=addon_dir.name):
                config = yaml.safe_load((addon_dir / "config.yaml").read_text())
                self.assertEqual(config["url"], "https://github.com/cococheaf/ha-addons")
                self.assertTrue(config["slug"])
                self.assertTrue(config["version"])

    def test_addon_slugs_are_unique(self):
        slugs = [
            yaml.safe_load((addon_dir / "config.yaml").read_text())["slug"]
            for addon_dir in ADDON_DIRS
        ]

        self.assertEqual(len(slugs), len(set(slugs)))

    def test_addon_icons_exist(self):
        for addon_dir in ADDON_DIRS:
            with self.subTest(addon=addon_dir.name):
                icon = addon_dir / "icon.png"
                self.assertTrue(icon.exists())
                self.assertEqual(icon.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
