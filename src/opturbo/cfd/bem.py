"""Compatibility exports for cfd module bem."""

from ..workflows.axisymmetric_2d.cfd.bem import loss_factor, solve, sources_from, performance

__all__ = ['loss_factor', 'solve', 'sources_from', 'performance']
