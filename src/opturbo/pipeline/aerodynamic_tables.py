"""Workflow-aware load, import, validation, and save operations for BEM CSV data."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from ..workflows import get_workflow
from ..workflows.axisymmetric_2d.cfd.resources import (
    CFD_TABLE_FILES,
    read_numeric_csv,
    validate_cfd_tables,
    validate_geometry_table,
    write_numeric_csv,
)


def workflow_cfd_tables_directory(workflow_id: str, application_root: Path) -> Path:
    """Return the selected workflow's independent CFD/BEM table folder."""
    return get_workflow(workflow_id, application_root).resources / "cfd_tables"


def load_cfd_tables(directory: Path) -> tuple[dict[str, list[list[float]]], list[str]]:
    """Read available tables while retaining errors that can be fixed in the panel."""
    tables: dict[str, list[list[float]]] = {}
    errors: list[str] = []
    for filename in CFD_TABLE_FILES:
        try:
            tables[filename] = read_numeric_csv(directory / filename)
        except (OSError, ValueError) as error:
            tables[filename] = []
            errors.append(str(error))
    return tables, errors


def validate_cfd_table_import(
    filename: str,
    rows: list[list[float]],
) -> None:
    """Validate one imported file's own format before cross-file save checks."""
    if filename not in CFD_TABLE_FILES:
        raise ValueError(f"Unknown aerodynamic table: {filename}")
    if filename == "ntnu_geometry.csv":
        validate_geometry_table(rows)
    elif filename == "s826_alpha.csv":
        if len(rows) < 2 or any(len(row) != 1 for row in rows):
            raise ValueError("s826_alpha.csv needs at least two rows with one angle in degrees per row.")
        alpha = [row[0] for row in rows]
        if any(right <= left for left, right in zip(alpha, alpha[1:])):
            raise ValueError("s826_alpha.csv angles must increase strictly.")
    elif filename == "s826_re.csv":
        if len(rows) != 1 or len(rows[0]) < 2:
            raise ValueError("s826_re.csv needs one row with at least two Reynolds numbers.")
        if any(value <= 0 for value in rows[0]) or any(
            right <= left for left, right in zip(rows[0], rows[0][1:])
        ):
            raise ValueError("s826_re.csv Reynolds numbers must be positive and strictly increasing.")
    elif filename in {"s826_cl.csv", "s826_cd.csv"}:
        # Cross-file dimensions are checked on Save, so axes and matrices can be imported in any order.
        if len(rows) < 2 or any(len(row) < 2 for row in rows):
            raise ValueError(f"{filename} must have at least two rows and two columns.")
        if filename == "s826_cd.csv" and any(value < 0 for row in rows for value in row):
            raise ValueError("Drag coefficients in s826_cd.csv must be zero or positive.")


def save_cfd_tables(
    directory: Path,
    tables: dict[str, list[list[float]]],
    filenames: Sequence[str],
) -> None:
    """Validate all tables, then replace only changed CSVs with rollback backups."""
    changed = set(filenames)
    unknown = changed.difference(CFD_TABLE_FILES)
    if unknown:
        raise ValueError("Unknown aerodynamic table(s): " + ", ".join(sorted(unknown)))
    if not changed:
        return
    validate_cfd_tables(tables)
    temporary: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    replaced: list[Path] = []
    missing_before: set[Path] = set()
    try:
        for filename in sorted(changed):
            target = directory / filename
            with tempfile.NamedTemporaryFile(prefix=f".{filename}.", suffix=".tmp",
                                             dir=directory, delete=False) as handle:
                temporary[target] = Path(handle.name)
            write_numeric_csv(temporary[target], tables[filename])
            if target.exists():
                with tempfile.NamedTemporaryFile(prefix=f".{filename}.", suffix=".bak",
                                                 dir=directory, delete=False) as handle:
                    backups[target] = Path(handle.name)
                shutil.copy2(target, backups[target])
            else:
                missing_before.add(target)
        for target, staged in temporary.items():
            os.replace(staged, target)
            replaced.append(target)
    except (OSError, ValueError) as error:
        rollback_errors: list[str] = []
        for target in reversed(replaced):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                elif target in missing_before:
                    target.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        suffix = (" Rollback also failed: " + "; ".join(rollback_errors)) if rollback_errors else ""
        raise OSError(f"{error}{suffix}") from error
    finally:
        for path in (*temporary.values(), *backups.values()):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
