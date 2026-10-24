# Tkinter interface

This folder composes the desktop window from focused view and interaction
modules. `window.py` owns shared window state, while project, design, workflow,
mesh-study, optimization, and monitor behavior live in separate mixins. The
small canvas plot, scrolling panel, and tooltip widgets are standard-library
Tkinter components.

GUI code reads settings and starts application services; engineering
calculations, persistence formats, and vendor commands live outside this
folder. `opturbo.app` re-exports the public application class and legacy test
helpers.
