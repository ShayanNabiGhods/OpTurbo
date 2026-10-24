# SpaceClaim resources

`profile_assembly.scscript` is the recorded SpaceClaim import/preparation script
used by the 2D axisymmetric workflow. The script depends on fixed body and face
identities and the configured handoff folder. The workflow copies the assembly
into that folder, runs SpaceClaim, then copies the resulting document into the
candidate's `02_spaceclaim/` output folder.
