"""Mesh-study candidate generation tests."""

import unittest

from opturbo.models import MeshSettings
from opturbo.workflows.axisymmetric_2d.mesh_study import automatic_mesh_settings


class MeshStudyTests(unittest.TestCase):
    """Check automatic candidate plans use the sole evenly spaced method."""

    def test_enabled_values_move_together_across_bounds(self):
        cases = automatic_mesh_settings(
            MeshSettings(),
            count=3,
            method="Quad",
            enabled_fields={"global_size_cm", "inflation_layers"},
            bounds={"global_size_cm": (1.0, 3.0), "inflation_layers": (2.0, 6.0)},
        )

        self.assertEqual([case.global_size_cm for case in cases], [1.0, 2.0, 3.0])
        self.assertEqual([case.inflation_layers for case in cases], [2, 4, 6])
        self.assertTrue(all(case.method == "Quad" for case in cases))

    def test_single_case_uses_range_midpoints(self):
        cases = automatic_mesh_settings(
            MeshSettings(),
            count=1,
            method="Default (ANSYS automatic)",
            enabled_fields={"global_size_cm", "growth_rate"},
            bounds={"global_size_cm": (1.0, 3.0), "growth_rate": (1.0, 1.2)},
        )

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].global_size_cm, 2.0)
        self.assertEqual(cases[0].growth_rate, 1.1)
        self.assertEqual(cases[0].method, "Default")


if __name__ == "__main__":
    unittest.main()
