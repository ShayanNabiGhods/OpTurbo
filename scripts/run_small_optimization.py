"""Run the small, reproducible V0.0.1 end-to-end optimization check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opturbo.models import GaSettings, ProjectConfig
from opturbo.optimizer import GeneticAlgorithm
from opturbo.pipeline import PipelineRunner
from opturbo.storage import ProjectStore, atomic_json


SELECTED_BOUNDS = {
    "geometry.duct_angle_deg": (-3.0, 3.0),
    "upper.crest_location": (0.33, 0.43),
    "upper.crest_height": (0.085, 0.12),
    "lower.crest_height": (-0.13, -0.09),
}


def build_config(output: Path, outer_iterations: int, fluent_iterations: int) -> ProjectConfig:
    """Create the deliberately small and conservative smoke-test setup."""
    config = ProjectConfig(project_name="V0.0.1 small optimization", save_dir=str(output))
    config.ga = GaSettings(population_size=2, generations=2, elite_count=1,
                           tournament_size=2, crossover_rate=0.85,
                           mutation_rate=0.25, mutation_scale=0.08, random_seed=17)
    config.cfd.max_outer_iterations = outer_iterations
    config.cfd.fluent_iterations = fluent_iterations
    config.cfd.relaxation = 0.2
    for variable in config.design_variables:
        variable.optimize = variable.key in SELECTED_BOUNDS
        if variable.key in SELECTED_BOUNDS:
            variable.minimum, variable.maximum = SELECTED_BOUNDS[variable.key]
    return config


def main() -> None:
    """Evaluate three candidates across two GA generations and save everything."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "workspace" / "v001_small_optimization")
    parser.add_argument("--outer-iterations", type=int, default=2)
    parser.add_argument("--fluent-iterations", type=int, default=20)
    args = parser.parse_args()

    config = build_config(args.output.resolve(), args.outer_iterations, args.fluent_iterations)
    store = ProjectStore(args.output.resolve())
    store.initialize(config)
    runner = PipelineRunner(ROOT, print)
    history: list[dict] = []

    def evaluate(genome: dict[str, float], generation: int, candidate: int):
        folder = store.candidate_dir(generation, candidate)
        try:
            result = runner.evaluate(config, genome, folder)
            return result["cp"], result
        except Exception as error:
            failure = {"cp": -1e30, "ct": None, "status": "failed",
                       "error": str(error), "candidate_dir": str(folder)}
            (folder / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
            print(f"Candidate failed: {error}")
            return failure["cp"], failure

    def record(event: dict) -> None:
        history.append(event)
        store.save_history(history)
        print(f"GA RESULT {event['evaluation']}: Cp={event['cp']:.8g} Ct={event.get('ct')}")

    optimizer = GeneticAlgorithm(config.design_variables, config.ga)
    best = optimizer.run(evaluate, on_result=record)
    atomic_json(store.root / "best" / "best_result.json", {
        "fitness": best.fitness, "genome": best.genome, **(best.result or {})})
    print("Selected variables:")
    for key, value in best.genome.items():
        print(f"  {key} = {value:.10g}")
    print(f"Best Cp: {best.fitness:.10g}")


if __name__ == "__main__":
    main()

