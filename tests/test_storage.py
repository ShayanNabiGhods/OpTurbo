"""Tests for project persistence and non-overwriting candidate folders."""

import tempfile
import unittest
from pathlib import Path

from opturbo.models import ProjectConfig
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


if __name__ == "__main__":
    unittest.main()
