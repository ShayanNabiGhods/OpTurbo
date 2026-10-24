"""Read Fluent surface report files."""

import re
from pathlib import Path

NUMBER_AT_END = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$")


def read_report(path, expected):
    """Return values from Fluent lines, in line-number order."""
    values = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if "line-" not in line:
            continue
        match = NUMBER_AT_END.search(line)
        if match:
            values.append(float(match.group(1)))
    if len(values) != expected:
        raise ValueError(f"{path}: expected {expected} values, found {len(values)}")
    return values
