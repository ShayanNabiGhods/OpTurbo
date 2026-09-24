"""Verify that GUI preview outlines follow the FreeCAD construction equations."""

import math
import unittest

from opturbo.models import GeometrySettings, default_design_variables
from opturbo.parsec import nested_parameters, validate_profile
from opturbo.preview import actuator_outline, hub_outline, outer_domain_outline, resolution_outline


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.settings = GeometrySettings()

    def test_outer_domain_matches_rectangle(self):
        points = outer_domain_outline(self.settings)
        self.assertEqual(points[0], (-2250.0, 0.0))
        self.assertEqual(points[2], (6750.0, 6750.0))
        self.assertEqual(points[0], points[-1])

    def test_resolution_inlet_is_quarter_circle(self):
        points = resolution_outline(self.settings, arc_points=9)
        center = (self.settings.resolution_origin_x + self.settings.resolution_inlet_radius,
                  self.settings.resolution_origin_r)
        for x, radius in points[:9]:
            distance = math.hypot(x - center[0], radius - center[1])
            self.assertAlmostEqual(distance, self.settings.resolution_inlet_radius)
        self.assertEqual(points[0], (self.settings.resolution_origin_x,
                                     self.settings.resolution_origin_r))

    def test_hub_and_actuator_match_freecad_extents(self):
        hub = hub_outline(self.settings)
        disk = actuator_outline(self.settings)
        self.assertAlmostEqual(min(x for x, _ in hub), -65.0)
        self.assertAlmostEqual(max(x for x, _ in hub), 735.0)
        self.assertAlmostEqual(max(r for _, r in hub), 45.0)
        self.assertAlmostEqual(min(x for x, _ in disk), -5.0)
        self.assertAlmostEqual(max(x for x, _ in disk), 0.0)
        self.assertAlmostEqual(max(r for _, r in disk), 450.0)

    def test_geometry_variables_do_not_pollute_parsec_dictionary(self):
        parameters = nested_parameters(default_design_variables())
        validate_profile(parameters)
        self.assertNotIn("geometry", parameters)


if __name__ == "__main__":
    unittest.main()
