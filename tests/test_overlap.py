"""Checks that overlapped CFD never starts before the matching mesh is ready."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from opturbo.models import ProjectConfig
from opturbo.pipeline.overlap import evaluate_generation
from opturbo.pipeline.runner import PreparedCandidate


class DelayedPreparationRunner:
    def __init__(self):
        self.second_mesh_started = threading.Event()
        self.allow_second_mesh = threading.Event()
        self.ready = set()
        self.fluent_started = []

    def emit(self, _message):
        pass

    def prepare(self, config, _genome, folder):
        index = int(folder.name.rsplit("_", 1)[-1])
        if index == 2:
            self.second_mesh_started.set()
            if not self.allow_second_mesh.wait(timeout=3):
                raise TimeoutError("test did not release candidate 2 meshing")
        self.ready.add(index)
        return PreparedCandidate(config, folder, folder / "mesh.msh")

    def finish(self, prepared):
        index = int(prepared.folder.name.rsplit("_", 1)[-1])
        if index not in self.ready:
            raise AssertionError(f"Fluent started before candidate {index} mesh was ready")
        self.fluent_started.append(index)
        return {"cp": float(index), "ct": 0.0, "candidate_dir": str(prepared.folder)}


class OverlapTests(unittest.TestCase):
    def test_candidate_result_is_yielded_while_next_mesh_runs_and_cfd_waits(self):
        runner = DelayedPreparationRunner()
        config = ProjectConfig()

        with tempfile.TemporaryDirectory() as root:
            def candidate_dir(_generation, index):
                return Path(root) / f"candidate_{index}"

            results = evaluate_generation(
                runner,
                config,
                [(1, {"x": 1.0}), (2, {"x": 2.0})],
                1,
                candidate_dir,
                lambda: False,
                lambda _event: None,
            )

            first = next(results)
            self.assertEqual(first[0], 1)
            self.assertTrue(runner.second_mesh_started.wait(timeout=1))
            self.assertEqual(runner.fluent_started, [1])

            with ThreadPoolExecutor(max_workers=1) as waiter:
                second_future = waiter.submit(next, results)
                self.assertFalse(second_future.done())
                self.assertEqual(runner.fluent_started, [1])
                runner.allow_second_mesh.set()
                second = second_future.result(timeout=3)

            self.assertEqual(second[0], 2)
            self.assertEqual(second[1], 2.0)
            self.assertEqual(runner.fluent_started, [1, 2])
            with self.assertRaises(StopIteration):
                next(results)


if __name__ == "__main__":
    unittest.main()
