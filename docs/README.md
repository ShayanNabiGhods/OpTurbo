# OpTurbo guides

`manual.pdf` is the task-oriented guide to the application tabs, controls, candidate lifecycle, and recovery. `theory.pdf` describes the geometry, axisymmetric CFD, BEM, coupling, performance coefficients, mesh sensitivity, and optimization methods used by this branch. The Markdown files alongside the PDFs are their editable source.

Regenerate both PDFs and the page map after editing the Markdown sources:

```powershell
python "scripts\build_documentation.py"
```

The GUI's question-mark buttons use `manual_help_index.json` to open the selected section by its stable named destination, rather than by a page number. Keep the section identifiers in the Markdown aligned with the index builder's `FIELD_TOPICS` map. Both guides use numbered chapters and subchapters in a continuous flow; the PDF outline mirrors that hierarchy.
