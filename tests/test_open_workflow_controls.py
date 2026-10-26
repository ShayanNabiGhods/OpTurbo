"""Workflow-specific tab and source-initialization controls."""

import unittest

from opturbo.gui.optimization_controls import OptimizationControlsMixin


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Control:
    def __init__(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def grid(self):
        self.visible = True


class _Notebook:
    def __init__(self):
        self.calls = []

    def tab(self, tab, **options):
        self.calls.append((tab, options))


class OpenWorkflowControlTests(unittest.TestCase):
    """Open workflow hides duct-only controls and restores them when switched."""

    def _app(self, workflow_id):
        source = _Value("previous_candidate")
        design = object()
        initialization = _Control()
        weight = _Control()
        class FakeApp(OptimizationControlsMixin):
            """Minimal app shell with the workflow controls under test."""

        app = FakeApp()
        app.workflow_id_var = _Value(workflow_id)
        app.notebook = _Notebook()
        app.design_tab = design
        app.optimization_tab = object()
        app.setting_controls = {
            ("cfd", "source_initialization"): [initialization],
            ("cfd", "previous_source_weight"): [weight],
        }
        app.field_vars = {("cfd", "source_initialization"): source}
        app._refresh_source_weight_control = lambda: None
        return app, source, design, initialization, weight

    def test_open_workflow_hides_design_and_forces_conservative_initialization(self):
        app, source, design, initialization, weight = self._app("axisymmetric_2d_open_turbine")

        OptimizationControlsMixin._apply_workflow_mode(app)

        self.assertIn((design, {"state": "hidden"}), app.notebook.calls)
        self.assertEqual(source.get(), "conservative")
        self.assertFalse(initialization.visible)
        self.assertFalse(weight.visible)

    def test_switching_back_restores_design_and_source_initialization(self):
        app, source, design, initialization, weight = self._app("axisymmetric_2d_open_turbine")
        OptimizationControlsMixin._apply_workflow_mode(app)
        app.workflow_id_var.set("axisymmetric_2d")

        OptimizationControlsMixin._apply_workflow_mode(app)

        self.assertIn((design, {"state": "normal"}), app.notebook.calls)
        self.assertEqual(source.get(), "previous_candidate")
        self.assertTrue(initialization.visible)
        self.assertTrue(weight.visible)


if __name__ == "__main__":
    unittest.main()
