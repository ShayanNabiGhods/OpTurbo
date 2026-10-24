"""Read geometry and design-variable values from saved OpTurbo result files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesignSnapshot:
    """Geometry and active design variables recovered from an OpTurbo JSON file."""

    design_type: str
    geometry: dict
    variables: dict[str, object]


def read_design_snapshot(path: str | Path, fallback_design_type: str = "flanged") -> DesignSnapshot:
    """Read either ``best_result.json`` or ``geometry_settings.json``."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The selected JSON file must contain a design object.")

    genome = payload.get("genome", {})
    genome = genome if isinstance(genome, dict) else {}
    configuration = payload.get("configuration", {})
    configuration = configuration if isinstance(configuration, dict) else {}
    configuration_geometry = configuration.get("geometry", {})
    configuration_geometry = configuration_geometry if isinstance(configuration_geometry, dict) else {}

    geometry_payload = payload.get("geometry_settings", {})
    geometry_payload = geometry_payload if isinstance(geometry_payload, dict) else {}
    is_geometry_file = source.name.lower() == "geometry_settings.json"
    if not geometry_payload and is_geometry_file:
        geometry_payload = payload

    candidate_dir = payload.get("candidate_dir")
    if candidate_dir and not geometry_payload:
        candidate_path = Path(str(candidate_dir))
        if not candidate_path.is_absolute():
            candidate_path = source.parent / candidate_path
        candidate_geometry = candidate_path / "01_geometry" / "geometry_settings.json"
        if candidate_geometry.is_file():
            loaded_geometry = json.loads(candidate_geometry.read_text(encoding="utf-8"))
            if isinstance(loaded_geometry, dict):
                geometry_payload = loaded_geometry

    geometry_data = geometry_payload.get("geometry", geometry_payload)
    geometry_data = geometry_data if isinstance(geometry_data, dict) else {}
    if not geometry_data:
        geometry_data = configuration_geometry

    parsec = geometry_payload.get("parsec", geometry_payload.get("flanged_curve", {}))
    if not isinstance(parsec, dict) or not parsec:
        parsec = payload.get("parsec", {})
    parsec = parsec if isinstance(parsec, dict) else {}

    raw_variables = payload.get("design_variables", configuration.get("design_variables", []))
    serialized_variables = {
        str(item.get("key")): item.get("value")
        for item in raw_variables
        if isinstance(item, dict) and item.get("key") is not None and item.get("value") is not None
    } if isinstance(raw_variables, list) else {}
    values: dict[str, object] = dict(serialized_variables)
    for section in ("upper", "lower"):
        section_values = parsec.get(section, {})
        if isinstance(section_values, dict):
            values.update({f"{section}.{name}": value for name, value in section_values.items()})
    values.update({f"geometry.{name}": value for name, value in geometry_data.items()})
    values.update({str(name): value for name, value in genome.items()})

    design_type = (geometry_data.get("design_type") or payload.get("design_type")
                   or configuration_geometry.get("design_type"))
    if design_type not in {"airfoil", "flanged"}:
        if any(key.startswith("upper.") for key in values):
            design_type = "airfoil"
        elif any(key in values for key in ("geometry.duct_flange_length", "geometry.duct_flange_angle_deg")):
            design_type = "flanged"
        else:
            design_type = fallback_design_type

    if is_geometry_file and not (geometry_data or parsec):
        raise ValueError("This geometry_settings.json contains no geometry or airfoil parameters.")
    if not is_geometry_file and not (genome or serialized_variables or geometry_data or parsec):
        raise ValueError("The JSON file contains no supported design values.")
    return DesignSnapshot(design_type, dict(geometry_data), values)
