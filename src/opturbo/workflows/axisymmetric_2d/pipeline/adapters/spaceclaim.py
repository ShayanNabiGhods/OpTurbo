"""SpaceClaim adapter for the fixed recorded CAD handoff."""

from pathlib import Path
import shutil
import sys

from .....models import ProjectConfig
from opturbo.pipeline.process import require_executable, run_streaming, windows_path
from .base import PipelineStage


class SpaceClaimStage(PipelineStage):
    """Run the packaged SpaceClaim script and collect its document."""

    def run(self, config: ProjectConfig, assembly: Path, output: Path) -> Path:
        self.runner.emit("[2/4] Running the fixed SpaceClaim script")
        handoff = Path(config.tools.handoff_dir)
        if sys.platform != "win32" and str(handoff).startswith("C:\\"):
            handoff = Path("/mnt/c") / str(handoff)[3:].replace("\\", "/")
        handoff.mkdir(parents=True, exist_ok=True)
        fixed_step = handoff / "profile_assembly.step"
        fixed_scdoc = handoff / "profile_assembly.scdoc"
        shutil.copy2(assembly, fixed_step)
        fixed_scdoc.unlink(missing_ok=True)
        script = self.runner.resources / "spaceclaim" / "profile_assembly.scscript"
        command = [require_executable(config.tools.spaceclaim, "SpaceClaim"), "/Headless=True",
                   f"/RunScript={windows_path(script)}", "/ExitAfterScript=True"]
        run_streaming(command, self.runner.root, output / "spaceclaim.log", self.runner.emit, self.runner.cancel)
        if not fixed_scdoc.exists():
            raise FileNotFoundError("SpaceClaim did not create profile_assembly.scdoc in its fixed handoff folder.")
        destination = output / "profile_assembly.scdoc"
        shutil.copy2(fixed_scdoc, destination)
        return destination
