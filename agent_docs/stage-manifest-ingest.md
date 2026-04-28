# Stage Manifest: ingest

Describes the purpose, input state, output state, and shared state hazards for
the ingest stage. Read this file before implementing any ingest tasks.

The manifest describes WHAT the stage must guarantee — not HOW to implement it.
Implementation decisions belong in task specs.

---

## Purpose
Read raw source files, enforce canonical schema, and write consolidated interim
Parquet ready for transform.

## Input state
- Raw source files in data/raw/
- Schema defined in data dictionary

## Output state
- Canonical column names enforced
- Data-dictionary dtypes enforced on all columns
- Nullable absent columns filled with NA
- Partitioned to max(10, min(n, 50))
- Unsorted

## Shared state hazards

**H1:** All columns must conform to the canonical schema before leaving ingest —
column names must match the data dictionary regardless of how the source file
names them.

**H2:** All columns must carry data-dictionary dtypes before leaving ingest —
pandas inference must not determine the schema of any column passed downstream.
Schema enforcement applies to all DataFrames produced within the stage regardless
of row count — including empty DataFrames. An empty DataFrame with untyped columns
will cause dtype mismatches when combined with typed partitions in the Dask graph,
and will fail at the Parquet write step. A zero-row DataFrame with correct column
names and dtypes is a valid schema-conformant output.

**H3:** Absent columns have two distinct error semantics:
- `nullable=yes` column absent from source → add as all-NA column at the correct
  dtype, do not raise. Its absence is expected and valid.
- `nullable=no` column absent from source → raise an error immediately.
  Its absence indicates a structural problem with the source file.

These two cases must never be collapsed into a single missing column handler.

**H4:** Parallelization of per-file reads must produce one delayed DataFrame per
file. The mechanism must guarantee each delayed unit computes to a DataFrame, not
a collection. Dask bag partitions compute to lists and cannot be passed to
dd.from_delayed — do not use Dask bag for per-file parallelization.

**H5:** Categorical columns use `pd.StringDtype()` in ingest.
Columns defined as categorical in the data dictionary are read and written as
`pd.StringDtype()` at the ingest stage. The transform stage applies
`CategoricalDtype(categories=[...])` with declared category sets.
