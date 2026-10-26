"""Check CSV validation and arbitrary radial-section counts."""

import tempfile
import math
import shutil
import unittest
from pathlib import Path

from opturbo.workflows.axisymmetric_2d.cfd.resources import (
    load_airfoil,
    load_blade,
    read_numeric_csv,
    validate_cfd_tables,
)
from opturbo.workflows.axisymmetric_2d.cfd.coupling import initial_sources
from opturbo.workflows.axisymmetric_2d.cfd.bem import performance, solve
from opturbo.workflows.axisymmetric_2d.cfd.fluent import write_journal
from opturbo.workflows.axisymmetric_2d.cfd.models import Flow, Turbine
from opturbo.cfd.resources import numbers as compatibility_numbers
from opturbo.pipeline.aerodynamic_tables import save_cfd_tables


APP_ROOT = Path(__file__).parents[1]
DUCTED_TABLES = APP_ROOT / "resources" / "workflows" / "axisymmetric_2d" / "cfd_tables"


class CfdTableResourceTests(unittest.TestCase):
    """Validate the shared data readers against bundled and custom tables."""

    def test_bundled_tables_are_complete_and_consistent(self):
        tables = {name: read_numeric_csv(DUCTED_TABLES / name) for name in (
            "ntnu_geometry.csv", "s826_alpha.csv", "s826_re.csv", "s826_cl.csv", "s826_cd.csv"
        )}
        validate_cfd_tables(tables)
        airfoil = load_airfoil(DUCTED_TABLES)
        self.assertEqual(len(airfoil.lift), len(airfoil.reynolds))
        self.assertTrue(all(len(row) == len(airfoil.alpha) for row in airfoil.lift))
        self.assertEqual(compatibility_numbers(DUCTED_TABLES / "s826_re.csv"),
                         read_numeric_csv(DUCTED_TABLES / "s826_re.csv"))

    def test_loader_supports_custom_geometry_row_counts_and_resampling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ntnu_geometry.csv").write_text(
                "0.10,0.04,20\n0.20,0.03,12\n0.35,0.02,4\n", encoding="utf-8"
            )
            source_sections = load_blade(root, stations=None)
            self.assertEqual(source_sections.radius, [0.10, 0.20, 0.35])
            self.assertEqual(source_sections.chord, [0.04, 0.03, 0.02])
            self.assertEqual(len(source_sections.dr), 3)

            for count in (2, 3, 7, 36, 64):
                with self.subTest(station_count=count):
                    blade = load_blade(root, stations=count)
                    self.assertEqual(len(blade.radius), count)
                    self.assertEqual(len(blade.chord), count)
                    self.assertEqual(len(blade.twist), count)
                    self.assertEqual(len(blade.dr), count)
                    self.assertAlmostEqual(blade.radius[0], 0.10)
                    self.assertAlmostEqual(blade.radius[-1], 0.35)

    def test_nondefault_radius_bounds_and_dynamic_station_names_reach_fluent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ntnu_geometry.csv").write_text(
                "0.10,0.04,20\n0.20,0.03,12\n0.35,0.02,4\n", encoding="utf-8"
            )
            blade = load_blade(root, stations=None)
            axial, tangential = initial_sources(blade)
            self.assertEqual(axial[0], 0.0)
            self.assertAlmostEqual(axial[-1], 0.0, places=10)
            self.assertEqual(len(tangential), 3)

            journal = root / "run.jou"
            write_journal(journal, blade, True, 1, hub_radius=0.10, rotor_radius=0.35)
            content = journal.read_text(encoding="utf-8")
            self.assertIn("/surface/line-surface line-01 0 0.1 0 0.15", content)
            self.assertIn("/surface/line-surface line-03 0 0.275 0 0.35", content)
            self.assertNotIn("line-04", content)

    def test_csv_reader_rejects_headers_and_ragged_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "custom.csv"
            for content in ("radius,chord,twist\n0.1,0.02,10\n", "1,2\n3\n"):
                with self.subTest(content=content):
                    source.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_numeric_csv(source)

    def test_polar_matrices_must_match_both_axes(self):
        tables = {name: read_numeric_csv(DUCTED_TABLES / name) for name in (
            "ntnu_geometry.csv", "s826_alpha.csv", "s826_re.csv", "s826_cl.csv", "s826_cd.csv"
        )}
        tables["s826_cl.csv"] = tables["s826_cl.csv"][:-1]
        with self.assertRaisesRegex(ValueError, "s826_cl.csv must have"):
            validate_cfd_tables(tables)

    def test_pipeline_saves_only_validated_changed_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("ntnu_geometry.csv", "s826_alpha.csv", "s826_re.csv",
                         "s826_cl.csv", "s826_cd.csv"):
                shutil.copy2(DUCTED_TABLES / name, root / name)
            tables = {name: read_numeric_csv(root / name) for name in (
                "ntnu_geometry.csv", "s826_alpha.csv", "s826_re.csv", "s826_cl.csv", "s826_cd.csv"
            )}
            original_drag = (root / "s826_cd.csv").read_bytes()
            tables["ntnu_geometry.csv"][0][1] += 0.001
            save_cfd_tables(root, tables, {"ntnu_geometry.csv"})
            self.assertAlmostEqual(read_numeric_csv(root / "ntnu_geometry.csv")[0][1], 0.0505)
            self.assertEqual((root / "s826_cd.csv").read_bytes(), original_drag)

            original_geometry = (root / "ntnu_geometry.csv").read_bytes()
            tables["s826_cl.csv"] = tables["s826_cl.csv"][:-1]
            with self.assertRaisesRegex(ValueError, "s826_cl.csv must have"):
                save_cfd_tables(root, tables, {"ntnu_geometry.csv"})
            self.assertEqual((root / "ntnu_geometry.csv").read_bytes(), original_geometry)

    def test_custom_polar_axis_and_matrix_sizes_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "s826_alpha.csv").write_text("-5\n0\n8\n", encoding="utf-8")
            (root / "s826_re.csv").write_text("50000,200000\n", encoding="utf-8")
            (root / "s826_cl.csv").write_text("-0.4,-0.3\n0,0.1\n0.8,1.0\n", encoding="utf-8")
            (root / "s826_cd.csv").write_text("0.08,0.06\n0.03,0.02\n0.09,0.07\n", encoding="utf-8")
            airfoil = load_airfoil(root)
            self.assertEqual(airfoil.alpha, [-5.0, 0.0, 8.0])
            self.assertEqual(airfoil.reynolds, [50000.0, 200000.0])
            self.assertEqual(len(airfoil.lift), 2)
            self.assertEqual(len(airfoil.lift[0]), 3)

    def test_coupled_bem_arrays_follow_multiple_station_counts(self):
        airfoil = load_airfoil(DUCTED_TABLES)
        flow = Flow(10.0, 1.187, 1.81e-5)
        turbine = Turbine(0.45, 0.045, 3, 100.0)
        for count in (2, 3, 8, 27, 64):
            with self.subTest(station_count=count):
                blade = load_blade(DUCTED_TABLES, stations=count)
                result = solve(flow, turbine, blade, airfoil,
                               [8.0] * count, [-2.0] * count)
                integrated = performance(flow, turbine, blade, result)
                self.assertEqual(len(result.dT), count)
                self.assertTrue(math.isfinite(integrated.cp))
                self.assertTrue(math.isfinite(integrated.ct))
                with self.assertRaisesRegex(ValueError, "same count"):
                    solve(flow, turbine, blade, airfoil, [8.0], [-2.0] * count)


if __name__ == "__main__":
    unittest.main()
