"""Builder for one configurable PARSEC duct profile."""

import math

import Part
from FreeCAD import Base

from .config import DesignParameters
from .freecad_helpers import checked
from .parsec import profile


PARSEC_DUCT = {
    "upper": {"leading_edge_radius": 0.0162187, "crest_location": 0.376723,
              "crest_height": 0.101977, "crest_curvature": -1.11136,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": -12.9184},
    "lower": {"leading_edge_radius": 0.00748922, "crest_location": 0.360,
              "crest_height": -0.11, "crest_curvature": 1.64354,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": 0.148211},
}


def duct(parameters: DesignParameters):
    """Build the single PARSEC duct with configurable chord, angle, and reversal."""
    x_values, upper, lower = profile(parameters.duct_points, parameters.parsec)
    if parameters.duct_reverse:
        upper, lower = [-value for value in upper], [-value for value in lower]
    angle = math.tan(math.radians(parameters.duct_angle_deg))
    top, bottom = [], []
    for x, y_upper, y_lower in zip(x_values, upper, lower):
        axial = parameters.duct_origin_x + parameters.duct_chord * x
        centre = parameters.duct_origin_r + parameters.duct_chord * x * angle
        top.append(Base.Vector(axial, centre + parameters.duct_chord * y_upper, 0))
        bottom.append(Base.Vector(axial, centre + parameters.duct_chord * y_lower, 0))
    upper_curve, lower_curve = Part.BSplineCurve(), Part.BSplineCurve()
    upper_curve.interpolate(top)
    lower_curve.interpolate(list(reversed(bottom)))
    wire = Part.Wire([upper_curve.toShape(), lower_curve.toShape()])
    return checked(wire, "PARSEC duct")
