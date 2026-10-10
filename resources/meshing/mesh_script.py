# ANSYS Mechanical/Meshing script
# These values are replaced by opturbo.pipeline.runner from geometry/config.py.
# Geometry values used for body selection
DOMAIN_HEIGHT_CM = 675
HUB_RADIUS_CM = 4.5
ACTUATOR_RADIAL_SPAN = 40.5
DOMAIN_ORIGIN_X_CM = -225
DOMAIN_LENGTH_CM = 900.0
DUCT_ORIGIN_X_CM = -7.2
DUCT_ORIGIN_R_CM = 47.5
DUCT_CHORD_CM = 20.0
DUCT_ANGLE_DEG = 0.0
RESOLUTION_LENGTH = 270.0
RESOLUTION_INLET_RADIUS = 90.0
# Only for flanged case
DUCT_FLANGE_LENGTH = 0
DUCT_FLANGE_ANGLE_DEG = 0
LOWER_TRAILING_EDGE_HEIGHT = 0

# Meshing sizes and properties
GLOBAL_SIZE_CM = 5.0
CURVATURE_ANGLE_DEG = 6.0
RESOLUTION_SIZE_CM = 0.5
DUCT_SIZE_CM = 0.3
HUB_SIZE_CM = 0.5
INFLATION_LAYERS = 5
INFLATION_MAX_THICKNESS_CM = 0.2

def create_face_worksheet_selection(name, rules):
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
    selection = Model.AddNamedSelection()
    selection.Name = name
    selection.ScopingMethod = GeometryDefineByType.Worksheet

    criteria = selection.GenerationCriteria

    for action, criterion, operator, value, upper in rules:
        criteria.Add(None)

        rule = criteria[criteria.Count - 1]

        # Explicitly define the worksheet action.
        # This prevents ANSYS from using the default "Add" action
        # for subsequent criteria.
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


def create_sizing(name, location, size_cm):
    sizing = mesh.AddSizing()
    sizing.Name = name
    sizing.Location = location
    sizing.ElementSize = Quantity(size_cm, "cm")

    return sizing


# Faces (worksheet selections, dimension driven).

# Largest face = outer fluid-domain face.
outer_domain = create_face_worksheet_selection("outer-fluid-domain", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.Size,
        SelectionOperatorType.Largest,
        "0 [cm^2]",
        None
    )
])


# Smallest face = actuator-disk face.
actuator_domain = create_face_worksheet_selection("actuator-disk-fluid-domain", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.Size,
        SelectionOperatorType.Smallest,
        "0 [cm^2]",
        None
    )
])


# Resolution domain:
# 1. Select faces smaller than the resolution-domain area.
# 2. Remove the smallest face (actuator disk).
resolution_area_limit = RESOLUTION_LENGTH * RESOLUTION_INLET_RADIUS

resolution_domain = create_face_worksheet_selection("resolution-fluid-domain", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.Size,
        SelectionOperatorType.LessThan,
        "{} [cm^2]".format(resolution_area_limit),
        None
    ),
    (
        SelectionActionType.Remove,
        SelectionCriterionType.Size,
        SelectionOperatorType.Smallest,
        "0 [cm^2]",
        None
    )
])

# Edges (worksheet selections are deliberately name based and dimension driven).

axis = create_edge_selection("axis", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationY,
        SelectionOperatorType.Equal,
        "0 [cm]",
        None
    )
])


inlet = create_edge_selection("inlet", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationX,
        SelectionOperatorType.Equal,
        "{} [cm]".format(DOMAIN_ORIGIN_X_CM),
        None
    )
])


outlet_x = DOMAIN_ORIGIN_X_CM + DOMAIN_LENGTH_CM

outlet = create_edge_selection("outlet", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationX,
        SelectionOperatorType.Equal,
        "{} [cm]".format(outlet_x),
        None
    )
])


outer_wall = create_edge_selection("outer-wall", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationY,
        SelectionOperatorType.Equal,
        "{} [cm]".format(DOMAIN_HEIGHT_CM),
        None
    )
])


import math

# Temp lines, it is not scalable!
clearance_CM = 0.1


duct_x_min = DUCT_ORIGIN_X_CM
duct_x_max = (
    DUCT_ORIGIN_X_CM
    + max(DUCT_FLANGE_LENGTH * math.cos(math.radians(DUCT_FLANGE_ANGLE_DEG)), 0)
    + DUCT_CHORD_CM * math.cos(math.radians(DUCT_ANGLE_DEG))
    + clearance_CM
)

duct_y_min = ACTUATOR_RADIAL_SPAN + HUB_RADIUS_CM + clearance_CM
duct_y_max = (
    DUCT_ORIGIN_R_CM
    + DUCT_FLANGE_LENGTH * math.sin(math.radians(DUCT_FLANGE_ANGLE_DEG))
    + DUCT_CHORD_CM * math.sin(math.radians(DUCT_ANGLE_DEG))
    + LOWER_TRAILING_EDGE_HEIGHT * DUCT_CHORD_CM
    + clearance_CM
)

duct_wall = create_edge_selection("duct-wall", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationX,
        SelectionOperatorType.RangeInclude,
        "{} [cm]".format(duct_x_min),
        "{} [cm]".format(duct_x_max)
    ),
    (
        SelectionActionType.Filter,
        SelectionCriterionType.LocationY,
        SelectionOperatorType.RangeInclude,
        "{} [cm]".format(duct_y_min),
        "{} [cm]".format(duct_y_max)
    )
])


hub_wall = create_edge_selection("hub-wall", [
    (
        SelectionActionType.Add,
        SelectionCriterionType.LocationY,
        SelectionOperatorType.RangeInclude,
        "{} [cm]".format(0),
        "{} [cm]".format(HUB_RADIUS_CM)
    ),
    (
        SelectionActionType.Remove,
        SelectionCriterionType.LocationY,
        SelectionOperatorType.Equal,
        "0 [cm]",
        None
    )
])


# Global mesh controls.
mesh = Model.Mesh

mesh.ElementSize = Quantity(GLOBAL_SIZE_CM, "cm")
mesh.CurvatureNormalAngle = Quantity(CURVATURE_ANGLE_DEG, "deg")
mesh.AutomaticMeshBasedDefeaturing = 1
mesh.DefeatureTolerance = Quantity(0.01, "cm")

# Local controls sized from the corresponding named selections.
resolution_sizing = create_sizing(
    "resolution-sizing",
    resolution_domain,
    RESOLUTION_SIZE_CM
)

duct_sizing = create_sizing(
    "duct-sizing",
    duct_wall,
    DUCT_SIZE_CM
)

hub_sizing = create_sizing(
    "hub-sizing",
    hub_wall,
    HUB_SIZE_CM
)

# Create combined selection for the inflation domain.
# Inflation will be applied to both the resolution domain and
# the actuator-disk fluid domain.
inflation_location = ExtAPI.SelectionManager.CreateSelectionInfo(
    SelectionTypeEnum.GeometryEntities)
for entity_id in resolution_domain.Location.Ids:
    inflation_location.Ids.Add(entity_id)
for entity_id in actuator_domain.Location.Ids:
    inflation_location.Ids.Add(entity_id)


# Create combined selection for the inflation boundaries.
# Inflation layers will be generated from both the hub wall
# and the duct wall.
inflation_boundary = ExtAPI.SelectionManager.CreateSelectionInfo(
    SelectionTypeEnum.GeometryEntities)
for entity_id in hub_wall.Location.Ids:
    inflation_boundary.Ids.Add(entity_id)
for entity_id in duct_wall.Location.Ids:
    inflation_boundary.Ids.Add(entity_id)


# Inflation.
inflation = mesh.AddInflation()
inflation.Location = inflation_location
inflation.BoundaryLocation = inflation_boundary
inflation.InflationOption = 0
inflation.NumberOfLayers = INFLATION_LAYERS
inflation.MaximumThickness = Quantity(INFLATION_MAX_THICKNESS_CM, "cm")


mesh.GenerateMesh()
