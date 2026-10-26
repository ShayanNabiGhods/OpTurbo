import argparse
import shutil
from pathlib import Path


MESH_SUFFIXES = (".msh", ".msh.gz", ".cas.h5", ".cas", ".cas.gz")


def has_mesh_suffix(path):
    return get_mesh_suffix(path) is not None


def get_mesh_suffix(path):
    name = path.name.lower()
    for suffix in MESH_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return None


def find_newest_mesh_file(project_files_dir):
    candidates = {}
    for path in project_files_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = get_mesh_suffix(path)
        if suffix is None:
            continue
        current = candidates.get(suffix)
        if current is None or path.stat().st_mtime > current.stat().st_mtime:
            candidates[suffix] = path

    if not candidates:
        return None

    for suffix in MESH_SUFFIXES:
        if suffix in candidates:
            return candidates[suffix]

    return None


def normalize_output_path(output_path, mesh_file):
    source_suffix = get_mesh_suffix(mesh_file)
    output_suffix = get_mesh_suffix(output_path)
    if output_suffix == source_suffix:
        return output_path
    if output_suffix is not None:
        return Path(str(output_path)[: -len(output_suffix)] + source_suffix)
    return Path(str(output_path) + source_suffix)


def main():
    parser = argparse.ArgumentParser(
        description="Extract the newest Fluent handoff mesh from a saved Workbench project."
    )
    parser.add_argument("--project", required=True, help="Path to the saved .wbpj file.")
    parser.add_argument("--output", required=True, help="Destination mesh/case file path.")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the temporary .wbpj and _files directory after extraction.",
    )
    args = parser.parse_args()

    project_path = Path(args.project)
    output_path = Path(args.output)
    project_files_dir = project_path.with_name(project_path.stem + "_files")

    if not project_files_dir.exists():
        raise FileNotFoundError(
            "Workbench project files directory was not found: "
            + str(project_files_dir)
        )

    mesh_file = find_newest_mesh_file(project_files_dir)
    if mesh_file is None:
        raise FileNotFoundError(
            "No Fluent mesh/case artifact was found under: " + str(project_files_dir)
        )

    final_output_path = normalize_output_path(output_path, mesh_file)
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mesh_file, final_output_path)
    print("Copied mesh artifact:")
    print("  source:", mesh_file)
    print("  output:", final_output_path)

    if args.cleanup:
        if project_files_dir.exists():
            shutil.rmtree(project_files_dir)
        if project_path.exists():
            project_path.unlink()


if __name__ == "__main__":
    main()
