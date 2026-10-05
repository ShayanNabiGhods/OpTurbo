"""Verify the published tip factor and preservation of the original model."""

import math
import unittest
from dataclasses import replace

from opturbo.cfd.bem import loss_factor, solve
from opturbo.cfd.models import Airfoil, Blade, Flow, Turbine
from opturbo.models import ProjectConfig


class TipLossTests(unittest.TestCase):
    """Exercise the two corrections independently of the external CFD solver."""

    def setUp(self):
        self.flow = Flow(10.0, 1.187, 1.81e-5)
        self.turbine = Turbine(0.45, 0.045, 3, 133.33333333333333)

    def test_prandtl_matches_original_tip_times_root(self):
        r, phi = 0.3, 0.25
        factor = lambda distance: 2 / math.pi * math.acos(math.exp(-1.5 * distance / (r * math.sin(phi))))
        expected = max(1e-4, factor(0.45 - r) * factor(r - 0.045))
        self.assertAlmostEqual(loss_factor(self.flow, self.turbine, r, phi), expected)

    def test_bontempo_matches_equation_and_global_tip_speed_ratio(self):
        turbine = replace(self.turbine, tip_loss_model="bontempo2025")
        for r in (0.045, 0.3, 0.449, 0.45):
            with self.subTest(radius=r):
                g = math.exp(-0.229 * (3 * 6 - 22.0116)) + 0.4427
                expected = 2 / math.pi * math.acos(math.exp(-g * 3 * (0.45-r) / (2*r*math.sin(0.25))))
                self.assertAlmostEqual(loss_factor(self.flow, turbine, r, 0.25), expected)
        self.assertGreater(loss_factor(self.flow, turbine, turbine.hub_radius, 0.25), 0.9)
        self.assertEqual(loss_factor(self.flow, turbine, turbine.radius, 0.25), 0)

    def test_model_changes_both_blade_loads(self):
        blade = Blade([0.4], [0.04], [5.0], [0.01], 0.005)
        airfoil = Airfoil([-90, 90], [1, 1e9], [[1, 1], [1, 1]], [[0.01, 0.01], [0.01, 0.01]])
        old = solve(self.flow, self.turbine, blade, airfoil, [8.0], [0.0])
        new = solve(self.flow, replace(self.turbine, tip_loss_model="bontempo2025"), blade, airfoil, [8.0], [0.0])
        ratio = new.loss[0] / old.loss[0]
        self.assertNotAlmostEqual(ratio, 1)
        self.assertAlmostEqual(new.dT[0] / old.dT[0], ratio)
        self.assertAlmostEqual(new.dQ[0] / old.dQ[0], ratio)

    def test_project_defaults_and_round_trip(self):
        self.assertEqual(ProjectConfig.from_dict({}).cfd.tip_loss_model, "prandtl")
        config = ProjectConfig()
        config.cfd.tip_loss_model = "bontempo2025"
        self.assertEqual(ProjectConfig.from_dict(config.to_dict()).cfd.tip_loss_model, "bontempo2025")

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            loss_factor(self.flow, replace(self.turbine, tip_loss_model="unknown"), 0.3, 0.25)
