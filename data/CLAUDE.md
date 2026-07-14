# data/ — scoped norms

Everything under `data/` is **gitignored** (size + dataset licenses). Layout:

```
data/raw/<dataset>/       pristine downloads, never modified in place
data/derived/<dataset>/   SpectrumGraph JSON per building per level (R0..R4 where derivable)
data/labels/<dataset>/    target files keyed by (building_id, target_name)
data/splits/              building-level split assignments (JSON, hashed) — small, TRACKED via results/
```

Rules:

- Acquisition commands, URLs, licenses, and expected checksums live in `docs/DATA.md`.
  Update it the moment a dataset lands — an external grader must be able to rebuild
  `data/` from that document alone.
- `data/raw/` is read-only after download. All processing writes to `data/derived/`
  through `topospec.data.*` builders, which stamp provenance (source dataset version,
  builder git SHA) into each output file's `meta` block.
- Every derived graph must pass `topospec validate` for its level before use. Builders
  fail loudly on malformed source plans; they never emit best-effort graphs silently —
  exclusions are logged to `data/derived/<dataset>/exclusions.jsonl` with reasons,
  and exclusion counts are reported in the paper.
- Labels are generated only by `topospec.labels.*` pipelines with manifests, same as
  experiment runs. Silver vs gold status is recorded per label file.
- Splits: building-level only (plan §9). Generate once with `topospec.experiments`
  tooling, store the assignment + its hash; never regenerate silently (that invalidates
  every downstream comparison).
