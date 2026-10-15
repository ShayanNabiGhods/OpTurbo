"""Consistent candidate failure classification and GA penalty records."""

from pathlib import Path

from ..storage import atomic_json


FAILURE_FITNESS = -1e30
_FLUENT_CRASH_MARKERS = (
    "sigsegv",
    "segmentation fault",
    "received signal sig =",
    "fatal error in one of the compute processes",
    "fatal failure in fluent",
    "access violation",
)


def failed_candidate(folder: Path, error: Exception | str, objective: str) -> dict:
    """Persist a finite penalty so a failed candidate cannot stop the GA."""
    folder = Path(folder)
    detail = str(error)
    evidence = [detail]
    cfd = folder / "04_cfd"
    logs = [cfd / "fluent_driver.log"]
    fluent = cfd / "fluent"
    if fluent.is_dir():
        logs.extend(fluent.glob("*error*.log"))
    for log in logs:
        try:
            evidence.append(log.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    crashed = any(marker in "\n".join(evidence).lower() for marker in _FLUENT_CRASH_MARKERS)
    status = "skipped_fluent_crash" if crashed else "failed"
    if crashed:
        detail = f"Fluent process crashed (SIGSEGV/native failure); candidate skipped. {detail}"
    result = {
        "cp": FAILURE_FITNESS,
        "ct": None,
        "fitness": FAILURE_FITNESS,
        "objective": objective,
        "status": status,
        "error": detail,
        "candidate_dir": str(folder),
    }
    atomic_json(folder / "failure.json", result)
    return result
