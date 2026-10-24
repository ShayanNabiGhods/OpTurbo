"""Genetic-algorithm settings."""

from dataclasses import dataclass


@dataclass
class GaSettings:
    """Genetic-algorithm controls."""

    population_size: int = 8
    generations: int = 10
    elite_count: int = 2
    tournament_size: int = 3
    crossover_rate: float = 0.85
    mutation_rate: float = 0.20
    mutation_scale: float = 0.10
    random_seed: int = 42
    overlap_preparation: bool = False
    objective: str = "cp"
