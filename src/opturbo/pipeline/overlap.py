"""Bounded overlap of one CFD evaluation with one same-generation preparation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterator

from ..models import ProjectConfig
from .failures import failed_candidate
from ..objectives import objective_value
from ..storage import atomic_json
from .runner import PipelineRunner, PreparedCandidate


def evaluate_generation(
    runner: PipelineRunner,
    config: ProjectConfig,
    candidates: list[tuple[int, dict[str, float]]],
    generation: int,
    candidate_dir: Callable[[int, int], Path],
    should_stop: Callable[[], bool],
    on_candidate: Callable[[dict], None],
) -> Iterator[tuple[int, float, dict]]:
    """Yield ordered fitness results; never prepare more than one candidate ahead.

    One worker owns Fluent and one owns the next candidate's preparation.
    Fluent results are yielded as soon as they finish, without waiting for the
    following mesh. The next Fluent job is submitted only after its preparation
    future has completed. Leaving the generator waits for active work and never
    starts an unprepared candidate's CFD evaluation.
    Only unevaluated members of this generation are supplied (elites excluded).
    """
    def failure(folder: Path, error: Exception) -> dict:
        """Persist a candidate failure and give it the standard GA penalty."""
        result = failed_candidate(folder, error, config.ga.objective)
        runner.emit(f"{folder.name}: {result['status']}; candidate skipped with penalty: {error}")
        return result

    def prepare(candidate: tuple[int, dict[str, float]]) -> tuple[Path, PreparedCandidate | dict]:
        """Allocate one unique folder and contain preparation failures."""
        index, genome = candidate
        folder = candidate_dir(generation, index)
        atomic_json(folder / "request.json", {"generation": generation, "candidate": index,
                                              "genome": genome, "configuration": config.to_dict()})
        runner.emit(f"Generation {generation}, candidate {index}: preparing stages 1–3")
        try:
            return folder, runner.prepare(config, genome, folder)
        except Exception as error:
            return folder, failure(folder, error)

    def finish(index: int, genome: dict[str, float], prepared: PreparedCandidate) -> dict:
        """Evaluate the active CFD candidate without accessing the shared handoff."""
        on_candidate({"generation": generation, "candidate": index, "genome": genome.copy()})
        runner.emit(f"Generation {generation}, candidate {index}: evaluating stage 4")
        try:
            return runner.finish(prepared)
        except Exception as error:
            return failure(prepared.folder, error)

    if not candidates or should_stop():
        return
    current = prepare(candidates[0])
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="opturbo-overlap") as executor:
        for position, (index, genome) in enumerate(candidates):
            if should_stop():
                return
            folder, prepared = current
            future = (executor.submit(finish, index, genome, prepared)
                      if isinstance(prepared, PreparedCandidate) else None)
            # Only n+1 is prepared while n runs. No future generation is known here.
            following = None
            if position + 1 < len(candidates) and not should_stop():
                following = executor.submit(prepare, candidates[position + 1])
            result = future.result() if future is not None else prepared
            fitness = (float(result["fitness"]) if "fitness" in result
                       else objective_value(result, config.ga.objective))
            yield index, fitness, result
            if following is None:
                return
            # Do not submit candidate n+1 to Fluent until its full preparation
            # (including ANSYS mesh generation) has returned successfully.
            current = following.result()
