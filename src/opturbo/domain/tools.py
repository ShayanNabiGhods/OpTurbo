"""External executable paths used by the axisymmetric workflow."""

from dataclasses import dataclass


@dataclass
class ToolPaths:
    """External executable paths and the immutable SpaceClaim handoff path."""

    freecad: str = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
    spaceclaim: str = r"C:\Program Files\ANSYS Inc\v242\scdm\SpaceClaim.exe"
    workbench: str = r"C:\Program Files\ANSYS Inc\v242\Framework\bin\Win64\RunWB2.exe"
    fluent: str = r"C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe"
    handoff_dir: str = r"C:\OpTurbo\Temp Files"
