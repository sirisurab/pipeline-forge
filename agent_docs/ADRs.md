# Architecture Decision Records

These records document the key architectural decisions made for this pipeline project.
Each ADR states the context, the decision, and — most importantly — the consequences
that must inform every implementation choice downstream.

Read this file in full before writing any task spec or implementing any pipeline module.

---

## ADR-001: Dask architecture

### Context
Single-machine pandas cannot handle 1M–5M row O&G datasets in memory. Parallel
processing is required at every data processing stage.

### Decision
Use Dask distributed scheduler for CPU-bound stages (ingest, transform, features).
Use Dask threaded scheduler for the I/O-bound acquire stage.

### Consequences
→ Scheduler choice is stage-dependent — acquire is I/O-bound (downloading files),
  ingest/transform/features are CPU-bound (data processing).
→ Partition count is a first-class design concern — it propagates across stage
  boundaries and must be treated as a contract, not an implementation detail.

---

## ADR-002: Scale-first design

### Context
O&G production datasets grow year-on-year. A pipeline that works correctly on a
single year's data must also work correctly when processing all years simultaneously.

### Decision
All transformation and feature engineering logic must be designed for scale from
the start — not optimized after correctness is established.

### Consequences
→ Performance requirements are first-class constraints, not post-correctness
  optimizations — a functionally correct but unscalable implementation is an
  incomplete implementation.
→ Code correct on 10K rows may fail silently at 4M rows — scale behavior must be
  reasoned about explicitly at design time, not discovered at runtime.
→ Per-row iteration operations are prohibited regardless of correctness — they
  become prohibitively slow at production data volumes (millions of rows,
  thousands of unique entities).
→ All per-entity aggregations (per-well, per-lease) must use vectorized grouped
  transformations — iterating over entity groups scales with unique entity count
  per partition and collapses at production volumes.
→ When choosing between vectorized approaches, prefer in this order: built-in
  vectorized operations first, grouped transformations second, row-wise
  application only as a last resort when no vectorized alternative exists.
→ String column transformations must use vectorized str accessor methods
  (str.extract, str.contains, str.replace, etc.) — .map() with a Python
  function on a string column is not a valid last resort. The str accessor
  is the vectorized path for string operations.

---

## ADR-003: Data dictionary as source of truth

### Context
O&G source data has inconsistent column naming, mixed nullable/non-nullable fields,
and categorical columns with known value sets. Inferring schema from data produces
incorrect types and silent failures downstream.

### Decision
The project data dictionary CSV is the single source of truth for all schema
decisions — column names, data-types, nullable status, and categorical values. No
schema information is inferred from the data itself.

### Consequences
→ Data-type mapping must always be derived from the data dictionary — never inferred from the data itself or from column    name heuristics.
→ Columns marked nullable=yes in the data dictionary must use nullable-aware
  data-type variants — standard non-nullable types cannot hold null values and
  data-APIs will upcast them (for example, in pandas api, non-nullable integer data-type is cast to floating point data-type) to accommodate nulls, causing downstream data-type mismatches when Dask validates partitions against
  expected schema.
→ Nullable status governs error handling for absent columns — the distinction
  between nullable=yes and nullable=no is not optional and cannot be collapsed
  into a single rule.
→ Categorical allowed values are defined in the data dictionary — values outside
  the declared set must be replaced with the appropriate null sentinel before
  casting, never allowed to propagate silently.
→ Meta derivation and function execution must share the same code path (for
  example, meta can be derived by calling the actual function on a minimal real
  input and slicing to zero rows). Any construction of meta that is separate from
  calling the actual function is prohibited, whether derived from the data
  dictionary, inferred from function logic, or extracted into a helper function.
→ Dask metadata must accurately reflect the actual output schema in column
  names, column order, and data-types — a mismatch causes silent wrong results or
  runtime errors at compute time.
→ Float null sentinel for float64 columns is np.nan, not pd.NA. pd.NA is
  valid only for nullable extension types (Int64, StringDtype, CategoricalDtype).
  Using pd.NA to fill a float64 column raises TypeError at compute time.

---

## ADR-004: Parquet as inter-stage format

### Context
Each pipeline stage writes output consumed by the next stage. The format and
partitioning of that output directly determines the performance and correctness
of downstream stages.

### Decision
All inter-stage data exchange uses partitioned Parquet files. Partition count
follows the formula max(10, min(n, 50)) at every stage write.

### Consequences
→ Partition count is a cross-stage contract — the writing stage is responsible
  for delivering well-partitioned output; the reading stage must not assume or
  re-establish partition count.
→ Writing one file per source entity (per-well, per-lease) is prohibited —
  high-cardinality partition keys produce tens of thousands of tiny files that
  degrade downstream performance severely.
→ The repartition step must be the last operation before writing Parquet output
  in every stage — operations after repartition may change partition count or
  destroy partition structure.
→ Row filtering using string operations must be done inside a partition-level
  function — Dask's string accessor is unreliable on columns produced by
  repartition or type casting operations.

---

## ADR-005: Dask task graph execution

### Context
Dask represents computations as a lazy task graph. How and when .compute() is
called determines whether the task graph is executed efficiently or redundantly.

### Decision
All independent computations within the same stage must be batched into a single
compute call. The task graph must remain lazy until the final write
operation in each stage.

### Consequences
→ Sequential compute calls on independent results are prohibited — each call
  replays the full upstream task graph independently, multiplying wall-clock
  time and memory pressure proportionally to the number of calls.
→ Batching independent computations into a single call allows Dask to execute
  shared upstream subgraphs once and parallelize independent branches — this
  is the correct execution model for multi-output stages.
→ The task graph must be kept lazy until the final Parquet write in each
  stage — intermediate compute calls inside transformation chains break the
  graph and prevent Dask from optimizing execution.
→ Any operation that materializes the dataset to derive a structural property
  (row count, partition count, schema) is prohibited — use graph-level
  properties instead.

---

## ADR-006: Dual-channel logging

### Context
Pipeline runs are long-running and may be unattended. Log output must be
accessible both during execution and after completion for different consumers —
a developer watching the terminal during a run, and post-run log review.

### Decision
All pipeline stages write logs to both the console and a log file simultaneously.
Log configuration (file path and level) is read from config.yaml.

### Consequences
→ Log setup must happen at pipeline startup before any stage runs — stages must
  not configure their own log handlers independently.
→ The log output directory must exist before any stage writes to it — it must be
  created at startup if absent.
→ Log files are runtime artifacts and must be excluded from version control.
→ Log level and file path are not hardcoded — they are read from the logging
  section of config.yaml so they can be changed without modifying code.

---

## ADR-007: Technology stack

### Context
The pipeline processes tabular O&G production data at scale on a single machine,
produces ML-ready output, and must be testable, type-safe, and reproducible.

### Decision
- Data processing: pandas for single-partition operations, Dask for distributed
  parallel processing across stages
- Storage format: Parquet for all inter-stage and output data
- Testing: pytest for all unit and integration tests
- Type checking: static type checking as part of the eval gate
- Python: 3.11 or higher
- HTTP acquisition: standard request and HTML parsing libraries

### Consequences
→ Parquet is the only permitted format for inter-stage data exchange — CSV and
  other row-based formats are prohibited for pipeline outputs due to performance
  and schema enforcement limitations at scale.
→ All test cases must be written for pytest — no other test frameworks are
  permitted.
→ Static type checking must pass as part of every eval run — type errors are
  treated as pipeline failures, not warnings.
→ Python version must be 3.11 or higher — features and type annotation syntax
  from earlier versions must not constrain implementation choices.
→ Browser automation tools are prohibited for data acquisition — standard HTTP
  request and HTML parsing libraries are sufficient and avoid the complexity and
  fragility of browser automation.

---

## ADR-008: Test strategy

### Context
The pipeline processes external data from URLs, writes files to disk, and
operates across multiple stages. Tests must be able to run without network
access or data files on disk in CI environments, while still supporting
full integration validation when data is available.

### Decision
All tests are written for pytest. Tests are marked to distinguish those
that require external resources from those that do not. Test requirements
are defined in test-requirements.xml as the authoritative source for all
test case specifications.

### Consequences
→ Every test must carry exactly one of two marks:
   - integration: requires network access or data files on disk at
     data/raw, data/processed, or data/interim
   - unit: requires neither network access nor data files on disk
→ No other test framework is permitted — all test cases across all
  pipeline stages use pytest.
→ Test requirements must be read from test-requirements.xml before
  writing any task spec — it is the authoritative source for what
  tests are required, not the coder's judgment.
→ Integration tests must write all stage outputs to pytest's `tmp_path`
  fixture — never to the project's `data/` directories. Stage functions
  under test must accept a config dict with output paths overridden to
  `tmp_path`. This ensures automatic cleanup and prevents test runs from
  corrupting pipeline data or leaving residual files in `data/interim/`,
  `data/features/`, or `data/processed/`.
