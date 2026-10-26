"""Check TSR sweep configuration and candidate isolation."""

import queue
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from opturbo.models import ProjectConfig
from opturbo.gui.optimization_worker import OptimizationWorkerMixin
from opturbo.gui.monitor_results import MonitorResultsMixin


class OpenTsrSweepWorkerTests(unittest.TestCase):
    def test_empty_run_history_clears_tsr_plot_without_invalid_x_values(self):
        class PlotStub:
            def __init__(self):
                self.series = None
                self.x_values = "unchanged"

            def set_series(self, series, x_values=None):
                self.series = series
                self.x_values = x_values

        plot = PlotStub()
        view = SimpleNamespace(history=[], run_tsr_plot=plot)
        MonitorResultsMixin._refresh_run_tsr_plot(view)
        self.assertEqual(plot.series, [("Cp", []), ("Ct", [])])
        self.assertIsNone(plot.x_values)

    def test_each_point_maps_tsr_to_rotor_speed_and_uses_a_new_candidate(self):
        config = ProjectConfig(workflow_id="axisymmetric_2d_open_turbine")
        config.cfd.flow_speed_m_s = 10.0
        config.cfd.rotor_radius_m = 0.5
        config.cfd.source_initialization = "previous_candidate"
        candidates = []
        evaluated = []

        class FakeStore:
            @staticmethod
            def candidate_dir(generation, index):
                candidates.append((generation, index))
                return Path(f"candidate_{index}")

        class FakeRunner:
            @staticmethod
            def evaluate(point_config, candidate):
                evaluated.append((point_config, candidate))
                return {"status": "completed", "cp": 0.4, "ct": 0.8}

        worker = SimpleNamespace(
            store=FakeStore(), history=[], events=queue.Queue(),
            stop_requested=threading.Event(), terminate_requested=threading.Event(),
            _runner=lambda: FakeRunner(),
        )
        OptimizationWorkerMixin._tsr_sweep_worker(worker, [4.0, 4.5], config)

        self.assertEqual(candidates, [(0, 1), (0, 2)])
        self.assertEqual([item[1] for item in evaluated], [Path("candidate_1"), Path("candidate_2")])
        self.assertEqual([item[0].cfd.omega_rad_s for item in evaluated], [80.0, 90.0])
        self.assertTrue(all(item[0].cfd.source_initialization == "conservative" for item in evaluated))
        results = [payload for kind, payload in list(worker.events.queue) if kind == "result"]
        self.assertEqual([item["tsr"] for item in results], [4.0, 4.5])
        self.assertEqual(config.cfd.source_initialization, "previous_candidate")


if __name__ == "__main__":
    unittest.main()
