# SpaceClaim resources

```text
spaceclaim/
├── profile_assembly.scscript   # Recorded import/preparation script
└── README.md                  # This resource map
```

`profile_assembly.scscript` opens the candidate STEP assembly, applies the
recorded SpaceClaim operations to known body/face identities, and saves the
prepared document. It relies on fixed vendor handoff paths configured in the
project model and adapter. Those paths and recorded selections are operational
contracts; changing them or substantially changing STEP topology can break the
script. The pipeline copies the resulting SCDOC into the candidate's
`02_spaceclaim/` archive after the stage.
