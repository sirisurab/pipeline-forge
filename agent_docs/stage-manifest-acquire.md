# Stage Manifest: acquire

Describes the purpose, input state, output state, and shared state hazards for
the acquire stage. Read this file before implementing any acquire tasks.

The manifest describes WHAT the stage must guarantee — not HOW to implement it.
Implementation decisions belong in task specs.

---

## Purpose
Download raw source files from external URLs for all configured years and deliver
them to data/raw/ for ingest.

## Input state
- config.yaml (URLs, years, output paths)

## Output state
Raw source files in data/raw/. Files may be missing for specific time periods /
leases / wells, in which case download fails — downstream stages must handle
missing files gracefully.

## Shared state hazards

**H1:** Acquire is I/O-bound — the scheduler must be chosen to match this workload,
not inherited from other stages.

**H2:** A failed download must not produce a file that appears valid — file existence
alone is not proof of validity.
