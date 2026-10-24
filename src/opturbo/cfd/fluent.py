"""Compatibility exports for cfd module fluent."""

from ..workflows.axisymmetric_2d.cfd.fluent import (
    CONVECTION_SCHEME_CODES,
    COUPLING_SCHEME_CODES,
    PRESSURE_SCHEME_CODES,
    VISCOUS_MODEL_COMMANDS,
    _model_equations,
    first_iteration_setup,
    run,
    write_journal,
)

__all__ = ['VISCOUS_MODEL_COMMANDS', 'CONVECTION_SCHEME_CODES', 'PRESSURE_SCHEME_CODES', 'COUPLING_SCHEME_CODES', 'first_iteration_setup', 'write_journal', 'run']
