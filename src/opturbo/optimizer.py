"""A compact, reproducible real-valued genetic algorithm."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable

from .models import GaSettings, VariableSpec


Genome = dict[str, float]
Evaluator = Callable[[Genome, int, int], tuple[float, dict]]


@dataclass
class Individual:
    """One candidate design and its evaluated fitness."""

    genome: Genome
    fitness: float | None = None
    result: dict | None = None


class GeneticAlgorithm:
    """Maximize an expensive objective using elitism and tournament selection."""

    def __init__(self, variables: list[VariableSpec], settings: GaSettings):
        self.variables = [variable for variable in variables if variable.optimize]
        self.settings = settings
        self.random = random.Random(settings.random_seed)
        if not self.variables:
            raise ValueError("Select at least one design variable for optimization.")
        if settings.population_size < 2:
            raise ValueError("Population size must be at least 2.")
        if not 0 <= settings.elite_count < settings.population_size:
            raise ValueError("Elite count must be smaller than the population.")

    def _random_genome(self) -> Genome:
        return {item.key: self.random.uniform(item.minimum, item.maximum) for item in self.variables}

    def _baseline_genome(self) -> Genome:
        return {item.key: item.value for item in self.variables}

    def _tournament(self, population: list[Individual]) -> Individual:
        size = min(self.settings.tournament_size, len(population))
        choices = self.random.sample(population, size)
        return max(choices, key=lambda item: item.fitness if item.fitness is not None else float("-inf"))

    def _child(self, first: Individual, second: Individual) -> Individual:
        genome: Genome = {}
        for variable in self.variables:
            a, b = first.genome[variable.key], second.genome[variable.key]
            if self.random.random() < self.settings.crossover_rate:
                weight = self.random.random()
                value = weight * a + (1.0 - weight) * b
            else:
                value = a if self.random.random() < 0.5 else b
            if self.random.random() < self.settings.mutation_rate:
                span = variable.maximum - variable.minimum
                value += self.random.gauss(0.0, self.settings.mutation_scale * span)
            genome[variable.key] = variable.clamp(value)
        return Individual(genome)

    def run(
        self,
        evaluate: Evaluator,
        on_result: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> Individual:
        """Run all generations and return the best evaluated individual."""
        population = [Individual(self._baseline_genome())]
        population.extend(Individual(self._random_genome()) for _ in range(self.settings.population_size - 1))
        best: Individual | None = None
        evaluation_number = 0
        for generation in range(1, self.settings.generations + 1):
            for index, individual in enumerate(population, 1):
                if should_stop and should_stop():
                    if best is None:
                        raise RuntimeError("Optimization stopped before any candidate finished.")
                    return best
                if individual.fitness is not None:
                    continue
                evaluation_number += 1
                fitness, result = evaluate(individual.genome, generation, index)
                individual.fitness, individual.result = fitness, result
                event = {
                    "evaluation": evaluation_number, "generation": generation,
                    "candidate": index, "fitness": fitness,
                    "genome": individual.genome, **result,
                }
                if on_result:
                    on_result(event)
                if best is None or fitness > (best.fitness if best.fitness is not None else float("-inf")):
                    best = Individual(individual.genome.copy(), fitness, result.copy())
            population.sort(key=lambda item: item.fitness if item.fitness is not None else float("-inf"), reverse=True)
            elites = [Individual(item.genome.copy(), item.fitness, item.result) for item in population[: self.settings.elite_count]]
            children = elites
            while len(children) < self.settings.population_size:
                children.append(self._child(self._tournament(population), self._tournament(population)))
            population = children
        if best is None:
            raise RuntimeError("The optimizer produced no result.")
        return best
