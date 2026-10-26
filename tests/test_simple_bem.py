"""Exercise the CFD-free BEM solver with bundled rotor and polar data."""

import math
from pathlib import Path
import unittest

from opturbo.simple_bem import run_tsr_sweep, tsr_values
from opturbo.workflows.axisymmetric_2d.cfd.models import Flow, Turbine
from opturbo.workflows.axisymmetric_2d.cfd.resources import load_airfoil, load_blade


class SimpleBemTests(unittest.TestCase):
    """Check interval handling and a complete local performance sweep."""

    def test_tsr_values_include_exact_endpoint(self):
        self.assertEqual(tsr_values(4, 8, 0.5), [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0])

    def test_tsr_values_stop_before_unreachable_endpoint(self):
        self.assertEqual(tsr_values(4, 8, 0.6), [4.0, 4.6, 5.2, 5.8, 6.4, 7.0, 7.6])

    def test_invalid_tsr_interval_is_rejected(self):
        for minimum, maximum, step in ((0, 8, 0.5), (8, 4, 0.5), (4, 8, 0), (4, 8, 0.001)):
            with self.subTest(interval=(minimum, maximum, step)):
                with self.assertRaises(ValueError):
                    tsr_values(minimum, maximum, step)

    def test_bundled_rotor_runs_without_fluent(self):
        resources = (Path(__file__).parents[1] / "resources" / "workflows"
                     / "axisymmetric_2d" / "cfd_tables")
        blade = load_blade(resources, stations=12)
        airfoil = load_airfoil(resources)
        flow = Flow(10.0, 1.187, 1.81e-5)
        turbine = Turbine(0.45, 0.045, 3, 133.33, tip_loss_model="prandtl")

        results = run_tsr_sweep(flow, turbine, blade, airfoil, 4, 5, 0.5)

        self.assertEqual([result.tip_speed_ratio for result in results], [4.0, 4.5, 5.0])
        self.assertAlmostEqual(results[0].omega_rad_s, 4 * flow.speed / turbine.radius)
        self.assertEqual(results[0].station_count, 12)
        for result in results:
            self.assertGreater(result.performance.power, 0)
            self.assertTrue(math.isfinite(result.performance.power))
            self.assertTrue(math.isfinite(result.performance.cp))
            self.assertTrue(math.isfinite(result.performance.ct))


if __name__ == "__main__":
    unittest.main()
