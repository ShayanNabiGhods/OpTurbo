"""Tests for project persistence and non-overwriting candidate folders."""

import tempfile
import unittest
from pathlib import Path

from opturbo.models import ProjectConfig, default_flanged_variables
from opturbo.storage import ProjectStore


class StorageTests(unittest.TestCase):
    def test_save_load_and_unique_candidate_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            config = ProjectConfig(project_name="Example", save_dir=folder)
            store = ProjectStore(Path(folder))
            store.initialize(config)
            loaded = ProjectStore.load(Path(folder))
            self.assertEqual(loaded.project_name, "Example")
            first = store.candidate_dir(1, 1)
            second = store.candidate_dir(1, 1)
            self.assertNotEqual(first, second)
            self.assertTrue(second.name.endswith("run02"))

    def test_old_parsec_only_project_gets_geometry_design_variables(self):
        config = ProjectConfig.from_dict({
            "geometry": {"duct_angle_deg": 3.0, "duct_chord": 215.0},
            "parsec_variables": [],
        })
        values = {item.key: item.value for item in config.design_variables}
        self.assertEqual(values["geometry.duct_angle_deg"], 3.0)
        self.assertEqual(values["geometry.duct_chord"], 215.0)

    def test_flanged_project_only_exposes_flanged_variables(self):
        config = ProjectConfig.from_dict({"geometry": {"design_type": "flanged"}})
        keys = {item.key for item in config.design_variables}
        self.assertEqual(keys, {item.key for item in default_flanged_variables()})
        self.assertNotIn("upper.crest_height", keys)

    def test_accessibility_preferences_round_trip(self):
        config = ProjectConfig.from_dict({
            "accessibility": {"theme": "dark", "text_scale": 125, "high_contrast": True},
        })
        self.assertEqual(config.accessibility.theme, "dark")
        self.assertEqual(config.accessibility.text_scale, 125)
        self.assertTrue(config.accessibility.high_contrast)


if __name__ == "__main__":
    unittest.main()
