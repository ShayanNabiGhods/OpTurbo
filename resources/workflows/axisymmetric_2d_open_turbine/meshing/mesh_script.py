# ANSYS Mechanical/Meshing script for the 2D axisymmetric open turbine.
# OpTurbo replaces the marked dimensions and mesh controls for each run.
DOMAIN_HEIGHT_CM = 675.0
HUB_RADIUS_CM = 4.5
DOMAIN_ORIGIN_X_CM = -225.0
DOMAIN_LENGTH_CM = 900.0
RESOLUTION_LENGTH_CM = 270.0
RESOLUTION_INLET_RADIUS_CM = 90.0

GLOBAL_SIZE_CM = 3.0
GROWTH_RATE = 1.1
CPU_CORES_FOR_PARALLEL_PART_MESHING = None
MESH_METHOD = "Quad"
CURVATURE_ANGLE_DEG = 5.0
RESOLUTION_SIZE_CM = 1.0
HUB_SIZE_CM = 0.3
INFLATION_ENABLED = True
INFLATION_LAYERS = 5
INFLATION_MAX_THICKNESS_CM = 0.2


def create_face_selection(name, rules):
    """Create a worksheet selection containing geometry faces."""
    selection = Model.AddNamedSelection()
    selection.Name = name
    selection.ScopingMethod = GeometryDefineByType.Worksheet
    criteria = selection.GenerationCriteria
    for action, criterion, operator, value, upper in rules:
        criteria.Add(None)
        rule = criteria[criteria.Count - 1]
        rule.Action = action
        rule.EntityType = SelectionType.GeoFace
        rule.Criterion = criterion
        rule.Operator = operator
        if upper is None:
            rule.Value = Quantity(value)
        else:
            rule.LowerBound = Quantity(value)
            rule.UpperBound = Quantity(upper)
    selection.Generate()
    return selection


def create_edge_selection(name, rules):
    """Create a worksheet selection containing geometry edges."""
    selection = Model.AddNamedSelection()
    selection.Name = name
    selection.ScopingMethod = GeometryDefineByType.Worksheet
    criteria = selection.GenerationCriteria
    for action, criterion, operator, value, upper in rules:
        criteria.Add(None)
        rule = criteria[criteria.Count - 1]
        rule.Action = action
        rule.EntityType = SelectionType.GeoEdge
        rule.Criterion = criterion
        rule.Operator = operator
        if upper is None:
            rule.Value = Quantity(value)
        else:
            rule.LowerBound = Quantity(value)
            rule.UpperBound = Quantity(upper)
    selection.Generate()
    return selection


def create_body_selection(name):
    """Select the fluid-domain body for the global mesh method."""
    selection = Model.AddNamedSelection()
    selection.Name = name
    selection.ScopingMethod = GeometryDefineByType.Worksheet
    selection.GenerationCriteria.Add(None)
    rule = selection.GenerationCriteria[selection.GenerationCriteria.Count - 1]
    rule.Action = SelectionActionType.Add
    rule.EntityType = SelectionType.GeoBody
    rule.Criterion = SelectionCriterionType.Size
    rule.Operator = SelectionOperatorType.Largest
    rule.Value = Quantity("0 [cm^3]")
    selection.Generate()
    return selection


def create_sizing(name, location, size_cm):
    """Attach a local element size to a named selection."""
    sizing = mesh.AddSizing()
    sizing.Name = name
    sizing.Location = location
    sizing.ElementSize = Quantity(size_cm, "cm")
    return sizing


outer_domain = create_face_selection("outer-fluid-domain", [
    (SelectionActionType.Add, SelectionCriterionType.Size,
     SelectionOperatorType.Largest, "0 [cm^2]", None)
])
whole_domain_body = create_body_selection("whole-domain-body")
actuator_domain = create_face_selection("actuator-disk-fluid-domain", [
    (SelectionActionType.Add, SelectionCriterionType.Size,
     SelectionOperatorType.Smallest, "0 [cm^2]", None)
])

# Exclude the actuator face from the local resolution-region sizing selection.
resolution_area_limit = RESOLUTION_LENGTH_CM * RESOLUTION_INLET_RADIUS_CM
resolution_domain = create_face_selection("resolution-fluid-domain", [
    (SelectionActionType.Add, SelectionCriterionType.Size,
     SelectionOperatorType.LessThan, "{} [cm^2]".format(resolution_area_limit), None),
    (SelectionActionType.Remove, SelectionCriterionType.Size,
     SelectionOperatorType.Smallest, "0 [cm^2]", None),
])

axis = create_edge_selection("axis", [
    (SelectionActionType.Add, SelectionCriterionType.LocationY,
     SelectionOperatorType.Equal, "0 [cm]", None)
])
inlet = create_edge_selection("inlet", [
    (SelectionActionType.Add, SelectionCriterionType.LocationX,
     SelectionOperatorType.Equal, "{} [cm]".format(DOMAIN_ORIGIN_X_CM), None)
])
outlet = create_edge_selection("outlet", [
    (SelectionActionType.Add, SelectionCriterionType.LocationX,
     SelectionOperatorType.Equal,
     "{} [cm]".format(DOMAIN_ORIGIN_X_CM + DOMAIN_LENGTH_CM), None)
])
outer_wall = create_edge_selection("outer-wall", [
    (SelectionActionType.Add, SelectionCriterionType.LocationY,
     SelectionOperatorType.Equal, "{} [cm]".format(DOMAIN_HEIGHT_CM), None)
])
hub_wall = create_edge_selection("hub-wall", [
    (SelectionActionType.Add, SelectionCriterionType.LocationY,
     SelectionOperatorType.RangeInclude, "0 [cm]", "{} [cm]".format(HUB_RADIUS_CM)),
    (SelectionActionType.Remove, SelectionCriterionType.LocationY,
     SelectionOperatorType.Equal, "0 [cm]", None),
])

mesh = Model.Mesh
mesh.ElementSize = Quantity(GLOBAL_SIZE_CM, "cm")
mesh.GrowthRateSF = GROWTH_RATE
if CPU_CORES_FOR_PARALLEL_PART_MESHING is not None:
    mesh.NumberOfCPUsForParallelPartMeshing = CPU_CORES_FOR_PARALLEL_PART_MESHING
mesh.CurvatureNormalAngle = Quantity(CURVATURE_ANGLE_DEG, "deg")
mesh.AutomaticMeshBasedDefeaturing = 1
mesh.DefeatureTolerance = Quantity(0.01, "cm")

method_types = {
    "Quad": MethodType.Automatic,
    "Tri": MethodType.AllTriAllTet,
    "MultiZone": MethodType.QuadTri,
}
if MESH_METHOD == "Default":
    pass
elif MESH_METHOD in method_types:
    automatic_method = mesh.AddAutomaticMethod()
    automatic_method.Location = whole_domain_body.Location
    automatic_method.Method = method_types[MESH_METHOD]
else:
    raise ValueError("Unsupported meshing method: {}".format(MESH_METHOD))

resolution_sizing = create_sizing("resolution-sizing", resolution_domain, RESOLUTION_SIZE_CM)
hub_sizing = create_sizing("hub-sizing", hub_wall, HUB_SIZE_CM)

if INFLATION_ENABLED:
    inflation_location = ExtAPI.SelectionManager.CreateSelectionInfo(
        SelectionTypeEnum.GeometryEntities)
    for entity_id in resolution_domain.Location.Ids:
        inflation_location.Ids.Add(entity_id)
    for entity_id in actuator_domain.Location.Ids:
        inflation_location.Ids.Add(entity_id)

    inflation_boundary = ExtAPI.SelectionManager.CreateSelectionInfo(
        SelectionTypeEnum.GeometryEntities)
    for entity_id in hub_wall.Location.Ids:
        inflation_boundary.Ids.Add(entity_id)

    inflation = mesh.AddInflation()
    inflation.Location = inflation_location
    inflation.BoundaryLocation = inflation_boundary
    inflation.InflationOption = 0
    inflation.NumberOfLayers = INFLATION_LAYERS
    inflation.MaximumThickness = Quantity(INFLATION_MAX_THICKNESS_CM, "cm")

mesh.GenerateMesh()
try:
    print("OPTURBO_MESH_CELL_COUNT={}".format(mesh.ElementCount))
except Exception:
    pass
