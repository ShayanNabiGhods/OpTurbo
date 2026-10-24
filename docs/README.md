# OpTurbo documentation files

```text
docs/
├── README.md                   # This documentation map and build instructions
├── manual.md                   # Editable user-facing operation guide
├── manual.pdf                  # Generated manual with named section anchors
├── manual_help_index.json      # GUI field-to-manual destination map
├── theory.md                   # Editable engineering and algorithm guide
├── theory.pdf                  # Generated theory guide
└── images/
    ├── cfd_bem_coupling.svg    # CFD/BEM coupling flow diagram
    └── genetic_algorithm.svg   # Genetic algorithm cycle diagram
```

The Markdown files are the editable source. The PDF files are generated
deliverables. The GUI reads `manual_help_index.json` to map a field's help
button to a stable named section destination in `manual.pdf`; the map is
regenerated together with the PDFs. Keep manual heading identifiers and the
builder's `FIELD_TOPICS` map aligned when changing sections.

Regenerate the PDFs and help index from the repository root:

```powershell
python scripts/build_documentation.py
```

Both guides use numbered chapter/subchapter headings and a continuous layout.
The PDF outline follows that hierarchy, and the SVG illustrations are included
from the source documents by the builder.
