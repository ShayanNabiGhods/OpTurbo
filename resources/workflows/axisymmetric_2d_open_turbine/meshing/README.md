# Open-turbine meshing resources

- `mesh_script.py` defines the duct-free 2D axisymmetric domain, named
  boundaries, actuator disk, and local mesh sizing. The runner applies project
  controls to a candidate-local copy.
- `extract_mesh_artifact.py` exports the Workbench mesh into that candidate.

These files are independent copies of the mesh-export utility and do not read
the ducted workflow's resource folder.
