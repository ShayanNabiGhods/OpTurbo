"""Check Monitor axis rendering without opening a GUI."""

import unittest
from unittest.mock import MagicMock

from opturbo.app import LinePlot


class MonitorPlotTests(unittest.TestCase):
    def render(self, values, log_ticks=False, y_step=None):
        """Capture canvas calls for a representative chart."""
        plot = MagicMock()
        plot.winfo_width.return_value = 700
        plot.winfo_height.return_value = 400
        plot.title, plot.x_label, plot.y_label = "Test", "Iteration (-)", "Value (-)"
        plot.palette = dict.fromkeys(("text", "axis", "muted", "grid"), "black")
        plot.series = [("Test", values)]
        plot.log_ticks, plot.y_step = log_ticks, y_step
        plot.COLORS = LinePlot.COLORS
        LinePlot.redraw(plot)
        return plot

    def test_residual_decades_and_minor_grid(self):
        plot = self.render([-5.2, -2.3], log_ticks=True)
        labels = [call.kwargs.get("text") for call in plot.create_text.call_args_list]
        for label in ("10^-6", "10^-5", "10^-4", "10^-3", "10^-2", "Iteration (-)", "1", "2"):
            self.assertIn(label, labels)
        self.assertTrue(any(call.kwargs.get("dash") == (2, 4) for call in plot.create_line.call_args_list))

    def test_outer_tenths(self):
        plot = self.render([0.22, 0.51], y_step=0.1)
        labels = [call.kwargs.get("text") for call in plot.create_text.call_args_list]
        for label in ("0.2", "0.3", "0.4", "0.5", "0.6"):
            self.assertIn(label, labels)

    def test_empty_and_single_point(self):
        self.render([])
        self.render([0.3], y_step=0.1)
