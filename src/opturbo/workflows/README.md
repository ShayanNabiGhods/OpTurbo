# Workflows

Each subpackage represents one engineering workflow and owns its geometry,
CAD, meshing, solver adapters, and resource selection. `selection.py` maps the
workflow ID saved in each project to its implementation. The mapping is a
plain Python dictionary so adding a workflow does not require a plugin loader.
Workflow-specific JSON options can live under
`ProjectConfig.workflow_settings[workflow_id]` and be validated by that
workflow's runner. The current 2D settings retain their established project
fields.

The current implementation is `axisymmetric_2d/`. Future workflows can add
packages such as `periodic_3d_blade/` and `periodic_3d_bladeless/`, give each a
runner factory that composes its own CAD, meshing, and solver adapters, and add
the class to `_WORKFLOW_TYPES`. Per-workflow settings can be kept under
`ProjectConfig.workflow_settings[workflow_id]`. Bundled resources belong in
`resources/workflows/<workflow_id>/`, and each workflow returns its own
resource root.
