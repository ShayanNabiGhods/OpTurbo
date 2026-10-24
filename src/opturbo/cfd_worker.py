"""Compatibility entry point for the axisymmetric Fluent/BEM worker."""

import sys
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APPLICATION_ROOT / "src"))

from opturbo.workflows.axisymmetric_2d.cfd_worker import build_config, main

if __name__ == "__main__":
    main()
