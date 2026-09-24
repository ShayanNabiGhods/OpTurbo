# OpTurbo contributor rules

These rules apply to every human or coding agent working in this repository.

1. Read `README.md` before changing the workflow.
2. Never edit the hardcoded paths or object selections inside
   `resources/spaceclaim/profile_assembly.scscript`. It must continue
   to read `C:\OpTurbo\Temp Files\profile_assembly.step` and write
   `C:\OpTurbo\Temp Files\profile_assembly.scdoc`.
3. Treat this as one standalone application. Engineering implementations live
   in `src/opturbo/geometry` and `src/opturbo/cfd`; external scripts, tables,
   cases, and UDF files live in `resources/`. GUI code must call them only
   through `src/opturbo/pipeline/`.
4. Store user runs outside the source tree through the workflow saving layer.
   A candidate folder must be self-describing and retain its configuration,
   logs, geometry, mesh, CFD results, and summary when available.
5. Prefer standard-library Python. Optional plotting must degrade gracefully
   when Matplotlib is unavailable.
6. Add type hints and short docstrings. Write for a beginner who understands
   basic Python but not this codebase.
7. Validate configuration before launching expensive external programs.
8. Do not delete or overwrite user results. New candidates receive unique,
   sequential folders and project saves are atomic.
9. Run `python -m unittest discover -s tests -v` and
   `python -m compileall -q src run.py` before committing.
10. Commit every coherent change to this repository. Use a short imperative
    subject, and leave the working tree clean when handing off.
