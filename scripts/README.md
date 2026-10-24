# Developer scripts

These are opt-in developer utilities, not part of the desktop startup path.
They import the same package services as the application. Run them from the
repository root so project-relative resource paths resolve as expected.

```text
scripts/
├── build_documentation.py   # Render docs/*.md as the two PDF guides
├── run_small_optimization.py # Start a small development optimization run
└── README.md                 # This script map
```

`build_documentation.py` writes the two committed guides; review the generated
PDFs after editing the Markdown sources. `run_small_optimization.py` is intended
for local development and requires the configured engineering tools to evaluate
candidates. Direct its output to a separate project/results folder, never into
source resources.
