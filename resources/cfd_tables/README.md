# CFD and BEM tables

The CSV and JSON files define the blade geometry, airfoil coefficients, and
operating-point data loaded by the axisymmetric CFD/BEM worker. The pipeline
copies this folder into each candidate's `04_cfd/resources/` directory before
the calculation. Keep engineering data in source control here; generated
results belong under the selected project folder.
