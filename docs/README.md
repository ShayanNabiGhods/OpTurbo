# OpTurbo documentation files

```text
docs/
├── README.md                   # This documentation map and build instructions
├── manual.md                   # Editable user-facing operation guide
├── manual.pdf                  # Generated user guide with chapter bookmarks
├── theory.md                   # Editable engineering and algorithm guide
├── theory.pdf                  # Generated theory guide
└── images/
    ├── cfd_bem_coupling.svg    # CFD/BEM coupling flow diagram
    └── genetic_algorithm.svg   # Genetic algorithm cycle diagram
```

The Markdown files are the editable source. The PDF files are generated
deliverables. A single Help button at the top of the app opens the complete
manual; the PDF outline lets readers navigate its chapters and sections.

Regenerate both PDFs from the repository root:

```powershell
python scripts/build_documentation.py
```

Both guides use numbered chapter/subchapter headings and a continuous layout.
The PDF outline follows that hierarchy, and the SVG illustrations are included
from the source documents by the builder.

The Manual's **Aerodynamic Data** chapter documents the headerless CSV formats
accepted by the Aerodynamic Data panel, including variable blade-section row
counts and the required angle/Reynolds polar matrix dimensions. The Theory
Guide explains how those tables are interpolated and used by the BEM solver.
Regenerate both PDF files after editing either Markdown source.
