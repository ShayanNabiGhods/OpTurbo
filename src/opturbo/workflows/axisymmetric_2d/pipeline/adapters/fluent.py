"""Fluent and BEM adapter for candidate CFD calculations."""

import json
from pathlib import Path
import re
import shutil
import sys

from .....models import ProjectConfig
from opturbo.pipeline.process import require_executable, run_streaming
from .base import PipelineStage


class FluentBEMStage(PipelineStage):
    """Prepare candidate inputs and run the Fluent/BEM worker."""

    def run(self, config: ProjectConfig, mesh: Path, output: Path,
            previous_candidate_sources: Path | None = None) -> dict:
        self.runner.emit("[4/4] Running persistent Fluent/BEM coupling")
        tables = output / "resources"
        fluent_workdir = output / "fluent"
        shutil.copytree(self.runner.resources / "cfd_tables", tables, dirs_exist_ok=True)
        shutil.copytree(self.runner.resources / "fluent", fluent_workdir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("iteration_history", "*.log", "latest_result.json"))
        cfd_settings = {
            "fluent": require_executable(config.tools.fluent, "Fluent"),
            "max_outer": config.cfd.max_outer_iterations,
            "tolerance": config.cfd.tolerance,
            "relax": config.cfd.relaxation,
            "fluent_iterations": config.cfd.fluent_iterations,
            "processors": config.cfd.processors,
            "flow_speed_m_s": config.cfd.flow_speed_m_s,
            "density_kg_m3": config.cfd.density_kg_m3,
            "viscosity_pa_s": config.cfd.viscosity_pa_s,
            "rotor_radius_m": config.cfd.rotor_radius_m,
            "hub_radius_m": config.cfd.hub_radius_m,
            # Match BEM's force-per-volume scaling to the generated mesh zone.
            "actuator_thickness_m": config.geometry.actuator_thickness / 1000.0,
            "blades": config.cfd.blades,
            "omega_rad_s": config.cfd.omega_rad_s,
            "pitch_deg": config.cfd.pitch_deg,
            "tip_loss_model": config.cfd.tip_loss_model,
            "bontempo_g_a": config.cfd.bontempo_g_a,
            "bontempo_g_b": config.cfd.bontempo_g_b,
            "bontempo_g_c": config.cfd.bontempo_g_c,
            "keep_iteration_data": config.cfd.keep_iteration_data,
            "source_initialization": config.cfd.source_initialization,
            "previous_source_weight": config.cfd.previous_source_weight,
            "previous_candidate_source_path": (
                str(previous_candidate_sources)
                if config.cfd.source_initialization == "previous_candidate"
                and previous_candidate_sources is not None
                and previous_candidate_sources.is_file() else None
            ),
            "fluent_settings": {
                "viscous_model": config.cfd.viscous_model,
                "residual_continuity": config.cfd.residual_continuity,
                "residual_x_velocity": config.cfd.residual_x_velocity,
                "residual_y_velocity": config.cfd.residual_y_velocity,
                "residual_swirl": config.cfd.residual_swirl,
                "residual_k": config.cfd.residual_k,
                "residual_epsilon": config.cfd.residual_epsilon,
                "residual_omega": config.cfd.residual_omega,
                "residual_nut": config.cfd.residual_nut,
                "pressure_scheme": config.cfd.pressure_scheme,
                "momentum_scheme": config.cfd.momentum_scheme,
                "swirl_scheme": config.cfd.swirl_scheme,
                "k_scheme": config.cfd.k_scheme,
                "epsilon_scheme": config.cfd.epsilon_scheme,
                "omega_scheme": config.cfd.omega_scheme,
                "nut_scheme": config.cfd.nut_scheme,
                "pressure_velocity_coupling": config.cfd.pressure_velocity_coupling,
            },
        }
        settings_path = output / "cfd_settings.json"
        settings_path.write_text(json.dumps(cfd_settings, indent=2), encoding="utf-8")
        worker = (
            self.runner.root / "src" / "opturbo" / "workflows"
            / "axisymmetric_2d" / "cfd_worker.py"
        )
        command = [sys.executable, str(worker), "--run-fluent",
                   "--stations", str(config.cfd.stations), "--max-outer",
                   str(config.cfd.max_outer_iterations), "--config", str(settings_path),
                   "--mesh", str(mesh), "--resources", str(tables),
                   "--workdir", str(fluent_workdir)]
        log = output / "fluent_driver.log"
        run_streaming(command, output, log, self.runner.emit, self.runner.cancel)
        latest = fluent_workdir / "latest_result.json"
        if latest.exists():
            return json.loads(latest.read_text(encoding="utf-8"))
        text = log.read_text(encoding="utf-8", errors="replace")
        match = re.findall(r"OPTURBO_RESULT Cp=([-+0-9.eE]+) Ct=([-+0-9.eE]+)", text)
        if not match:
            raise RuntimeError("Fluent finished without a readable Cp/Ct result.")
        cp, ct = match[-1]
        return {"cp": float(cp), "ct": float(ct)}
