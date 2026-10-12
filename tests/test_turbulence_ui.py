"""Check turbulence UI filtering without opening a desktop window."""

import unittest
from unittest.mock import MagicMock, patch

from opturbo.app import OpTurboApp, TURBULENCE_EQUATIONS, TURBULENCE_FIELDS
from opturbo.cfd.fluent import _model_equations


class TurbulenceUiTests(unittest.TestCase):
    """Keep displayed controls consistent with Fluent's active equations."""

    def test_models_match_solver(self) -> None:
        for model, equations in TURBULENCE_EQUATIONS.items():
            self.assertEqual(equations, _model_equations(model))

    def test_switch_filters_controls_and_preserves_variables(self) -> None:
        app = MagicMock()
        app.field_vars = {("cfd", name): MagicMock() for name in TURBULENCE_FIELDS}
        original = app.field_vars.copy()
        with patch("opturbo.app.ttk"), patch("opturbo.app.ToolTip"):
            for model, equations in TURBULENCE_EQUATIONS.items():
                app.field_vars[("cfd", "viscous_model")].get.return_value = model
                with patch("opturbo.app.ttk.Entry") as entry, patch("opturbo.app.ttk.Combobox") as combo:
                    OpTurboApp._refresh_turbulence_controls(app)
                    self.assertEqual(entry.call_count, len(equations))
                    self.assertEqual(combo.call_count, len(equations) + 1)
                    shown = [call.kwargs["textvariable"] for call in entry.call_args_list]
                    self.assertEqual(shown, [original[("cfd", f"residual_{eq}")] for eq in equations])
                self.assertEqual(app.field_vars, original)
