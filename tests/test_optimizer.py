"""Tests for deterministic genetic optimization behavior."""

import unittest

from opturbo.models import GaSettings, VariableSpec
from opturbo.optimizer import GeneticAlgorithm


class OptimizerTests(unittest.TestCase):
    def test_ga_preserves_bounds_and_improves_baseline(self):
        variables = [VariableSpec("upper.test", "Test", 0.0, -1.0, 1.0, True)]
        settings = GaSettings(population_size=8, generations=5, elite_count=1,
                              mutation_rate=0.5, random_seed=7)
        seen = []

        def evaluate(genome, generation, index):
            value = genome["upper.test"]
            seen.append(value)
            return -(value - 0.65) ** 2, {"cp": -(value - 0.65) ** 2, "ct": 0.0}

        best = GeneticAlgorithm(variables, settings).run(evaluate)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in seen))
        self.assertGreater(best.fitness, -(0.0 - 0.65) ** 2)

    def test_requires_selected_variable(self):
        with self.assertRaises(ValueError):
            GeneticAlgorithm([VariableSpec("x.y", "Y", 0, -1, 1, False)], GaSettings())


if __name__ == "__main__":
    unittest.main()

