# Ducted SpaceClaim resource

`profile_assembly.scscript` is the recorded ducted geometry preparation
script. The pipeline stages a candidate-local copy and runs it in SpaceClaim
to create the SCDOC used by ANSYS Meshing.

Keep its hardcoded STEP/SCDOC paths and object selections unchanged. The
workflow relies on those recorded selections when preparing ducted geometry.
