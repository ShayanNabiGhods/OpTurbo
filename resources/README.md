# Bundled resources

These are inputs consumed by the current 2D axisymmetric workflow: recorded
SpaceClaim commands, ANSYS Meshing scripts, Fluent/UDF files, and BEM tables.
`Axisymmetric2DWorkflow.resources` selects this existing directory so the
recorded SpaceClaim handoff and vendor assets keep their established paths.

Do not place generated candidate outputs here. They belong in the user's
selected project folder. New workflows should keep their own source resources
under `resources/workflows/<workflow_id>/` and resolve that directory through
their workflow definition.
