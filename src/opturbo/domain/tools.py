"""External executable paths used by the axisymmetric workflow."""

from dataclasses import dataclass


@dataclass
class ToolPaths:
    """External executable paths and the OpenFOAM WSL launch settings."""

    freecad: str = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
    spaceclaim: str = r"C:\Program Files\ANSYS Inc\v242\scdm\SpaceClaim.exe"
    workbench: str = r"C:\Program Files\ANSYS Inc\v242\Framework\bin\Win64\RunWB2.exe"
    fluent: str = r"C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe"
    handoff_dir: str = r"C:\OpTurbo\Temp Files"
    wsl_executable: str = r"C:\Windows\System32\wsl.exe"
    wsl_distribution: str = "Ubuntu24"
    openfoam_bashrc: str = "/opt/openfoam14/etc/bashrc"
    wsl_mount_root: str = "/mnt"
    wsl_work_root: str = "/tmp/opturbo-openfoam"
