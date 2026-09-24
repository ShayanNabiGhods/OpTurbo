# ANSYS Mechanical/Meshing script
# These values are replaced by opturbo.pipeline.runner from geometry/config.py.
DOMAIN_HEIGHT_CM = 67.5
HUB_RADIUS_CM = 4.5
DOMAIN_ORIGIN_X_CM = -22.5
DOMAIN_LENGTH_CM = 90.0
DUCT_ORIGIN_X_CM = -7.2
DUCT_ORIGIN_R_CM = 47.5
DUCT_CHORD_CM = 20.0
DUCT_ANGLE_DEG = 0.0
GLOBAL_SIZE_CM = 5.0
CURVATURE_ANGLE_DEG = 6.0
RESOLUTION_SIZE_CM = 0.5
DUCT_SIZE_CM = 0.3
HUB_SIZE_CM = 0.5
INFLATION_LAYERS = 5
INFLATION_MAX_THICKNESS_CM = 0.2


def create_body_selection(name, body_ids):
    selection = Model.AddNamedSelection()
    selection.Name = name

    info = ExtAPI.SelectionManager.CreateSelectionInfo(
        SelectionTypeEnum.GeometryEntities
    )

    info.Ids = body_ids
    selection.Location = info

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


# Bodies (the default body ID system is appropriate here).
outer_domain = create_body_selection("outer-fluid-domain", [5])
resolution_domain = create_body_selection("resolution-fluid-domain", [6])
actuator_domain = create_body_selection("actuator-disk-fluid-domain", [4])


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

duct_x_min = DUCT_ORIGIN_X_CM

duct_x_max = (
    DUCT_ORIGIN_X_CM
    + DUCT_CHORD_CM * math.cos(math.radians(DUCT_ANGLE_DEG))
)

# Temp line, it is not scalable!
duct_rise = 2.45

duct_y_min = DUCT_ORIGIN_R_CM - duct_rise
duct_y_max = DUCT_ORIGIN_R_CM + duct_rise

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
mesh.AutomaticMeshBasedDefeaturing = 0


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
