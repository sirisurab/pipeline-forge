# Pipeline Testing Errors — Manual Fixes and Constraint Updates

## Error Table

| # | Error | Pipeline | Stage | What failed | Manual fix | Constraint added/modified | Root cause category |
|---|---|---|---|---|---|---|---|
| 1 | DocNum non-nullable int64 fails on nulls in 2020 data | COGCC | Ingest | pd.read_csv raises on NA in int64 column | Changed to pd.Int64Dtype() in dtype map; updated data dictionary | dtypes: nullable=yes → pd.Int64Dtype() mapping | Coder didn't use data dictionary; inferred dtype from column name |
| 2 | OOM — 4.3M rows loaded into single worker | COGCC | Transform | Ingest wrote 1 partition; transform read it as 1 partition | Changed repartition formula to max(10, min(npartitions, 50)) in transform and features | dask-parquet: repartition formula codified as single constraint for all stages | Coder focused on task in isolation — didn't reason about partition count propagation across stages |
| 3 | Sort order destroyed by set_index shuffle | KGS | Transform | Sort by production_date before set_index; shuffle destroyed order | Moved sort to after set_index + repartition via map_partitions | transform: set_index → repartition → sort sequence | Coder focused on task in isolation — didn't reason about Dask shuffle side effects |
| 4 | map_partitions meta column order mismatch | COGCC | Features | Rolling meta loop was window→fluid; function was fluid→window | Derived meta by calling function on ddf._meta.copy() | dtypes: meta must match function output in names, order, and dtypes; derive from function call | Coder replicated loop manually instead of using function as source of truth |
| 5 | Non-vectorized groupby operations | KGS | Transform / Features | Per-well Python loops at scale — too slow | Not yet fixed in code; added as constraint | vectorization: no iterrows/itertuples/for-loops; compute: batch all dask.compute() calls | Coder optimized for correctness only, not scale — task spec didn't specify performance requirements |
| 6 | Acquire stage slow with distributed scheduler | KGS | Acquire | I/O-bound downloads using distributed LocalCluster — process overhead dominated | Switched to scheduler="threads"; lazy distributed init in pipeline.py | build-env: acquire uses threaded scheduler; distributed initialized lazily before ingest | Coder applied same scheduler pattern to all stages without distinguishing I/O vs compute workloads |
| 7 | Nullable columns absent from 2025 CSV raise IngestError | COGCC | Ingest | New ingest treated all schema columns as required; 2025 file missing GasShrinkage, BomInvent, EomInvent | Changed to fill missing nullable columns with NA; only raise on non-nullable missing | dtypes: nullable columns absent from source must be filled with NA, not raise | Coder enforced schema strictly but didn't distinguish nullable vs non-nullable — data dictionary had the info but task spec didn't connect it to error handling behavior |
| 8 | Non-canonical column names from 2025 CSV passed downstream | COGCC | Ingest | 2025 CSV has GasSrinkage (typo), BOMInvent, EOMInvent (case variants) — pandas read all columns including non-canonical ones; extra columns propagated to interim Parquet and would cause meta mismatch in transform | Added case-insensitive rename step after read; drop columns with no canonical match with WARNING | dtypes: normalize column names to canonical schema via case-insensitive match after reading; rename matches, drop non-matches with WARNING | Task spec had no instruction on column name normalization — coder passed all CSV columns through without checking against canonical schema |
| 9 | Dask bag used for per-file parallelization — returns lists not DataFrames | KGS | Ingest | Task 04 spec prescribed "Create a Dask bag from the list of file paths"; coder implemented `bag.map(...).to_delayed()` → `dd.from_delayed()`; Dask bag's `.to_delayed()` produces delayed objects that compute to lists, not DataFrames; `dd.from_delayed` fails with "got `list`" | Replace bag with `dask.delayed` per file in a loop; derive meta from `read_raw_file(files[0], schema).iloc[0:0]` | stage-manifest-ingest: parallelization must use dask.delayed per file, not Dask bag; Dask bag partitions compute to lists | Task-writer prescribed a specific Dask API (Dask bag) as the mechanism rather than intent; no constraint in stage manifest defined the correct pattern |
| 10 | `_build_meta_schema` helper rebuilt despite ADR-003 update | KGS | Ingest | ADR-003 updated to say "meta derivation and function execution must share the same code path"; Task 04 spec said "Build the meta DataFrame by constructing an empty pandas DataFrame with all canonical columns at their resolved dtypes — derived from the same resolve_pandas_dtype path"; coder interpreted "same resolve_pandas_dtype path" as "use the same dtype resolver function" not "call the actual reader function" | Remove `_build_meta_schema`; derive meta from `read_raw_file(files[0], schema).iloc[0:0]` | ADR-003 consequence strengthened; task-writer must not prescribe meta construction in task specs — defer to ADR-003 | Task spec overwrote the ADR with a more specific but incorrect instruction; ADR is authoritative but task spec contradicted it — coder followed the more specific (task spec) over the more general (ADR) |
| 11 | NavigableString type check fails on acquire.py — recurring across KGS and COGCC | Both | Acquire | mypy flags subscript of BeautifulSoup `NavigableString` with string key; coder fixes wrong `type: ignore` error code in one eval loop, fixes actual type in next loop; adds 2 extra eval loops per pipeline | Add `isinstance(element, Tag)` guard before subscripting BeautifulSoup elements | stage-manifest-acquire: BeautifulSoup tag subscripting must use isinstance(element, Tag) guard; never use type: ignore as first fix for BS4 types | No constraint about BS4 Tag/NavigableString union typing; coder consistently reaches for `type: ignore` rather than type-safe guard |
| 12 | Makefile pipeline target double-runs all stages | Both | Build | `pipeline: acquire ingest transform features` dependencies + CLI command body caused every stage to run twice | Removed Make-level stage dependencies from pipeline target; entry point invoked once for all stages | build-env-manifest: pipeline target must use exactly one invocation approach; never combine dependency chaining AND recipe body | Task spec said "pipeline target must depend on individual stage targets in sequence" — ambiguous; coder combined both dependency chaining and CLI invocation |
| 13 | `pd.NA` used as null sentinel for float64 absent columns — TypeError at fill | KGS | Ingest | `pd.array([pd.NA] * len(df), dtype=np.float64)` raises TypeError: float() argument must be a string or a real number, not 'NAType'; 5 unit tests failed on this; absent nullable float columns cannot be filled with pd.NA | Use `np.nan` for float columns; use `pd.NA` only for Int64 and StringDtype | dtypes: null sentinel for float columns is np.nan not pd.NA; pd.NA is only valid for nullable extension types (Int64, StringDtype, CategoricalDtype) | Coder applied pd.NA uniformly as the null sentinel without distinguishing extension dtype nulls (pd.NA) from numpy dtype nulls (np.nan) |
| 14 | `np.True_ is True` / `np.False_ is False` identity assertions fail in tests | KGS | Transform | pytest `assert result["col"].iloc[0] is True` fails because pandas boolean operations return numpy scalar np.True_ not Python bool True; identity check `is` fails where equality `==` would pass | Replace `is True` / `is False` with `== True` / `== False` or use `.bool()` | tests: never use `is True` / `is False` for numpy/pandas boolean values; use `==` or cast to Python bool | Coder wrote test assertions using Python identity semantics (`is`) rather than value equality (`==`) for numpy scalar types |
| 15 | E712 ruff: `== False` / `== True` comparisons in test assertions | KGS | Tests | ruff flags `assert (result["has_date_gap"] == False).all()` as E712; requires `not result["has_date_gap"]` or `~result["has_date_gap"]`; conflicts with fix for error 14 above | Use `~df["col"]` (bitwise not) for Series negation; use `.all()` on the negated Series | tests: use `~series` for boolean negation on pandas Series; avoid both `== False` (ruff E712) and `is False` (numpy scalar identity issue) | Coder unaware of ruff E712 rule; resolved `is False` issue by switching to `== False` which trades one linting error for another |
| 16 | Unused variable assignments in tests — F841 ruff | KGS | Tests | Variables assigned but never referenced (`df = gas_oil_df.copy()`, `report_path = tmp_path / ...`) flagged as F841 by ruff | Remove unused assignments | tests: assign variables only if they are used in the test body; use expressions directly in assertions where the value is not reused | Coder wrote setup boilerplate variable assignments without verifying they are referenced in test assertions |
| 17 | Non-existent build backend `setuptools.backends.legacy:build` in pyproject.toml — recurring | KGS | Build | `make install` fails with `BackendUnavailable: Cannot import 'setuptools.backends.legacy'`; recurred in run 8 despite constraint added after run 4; module does not exist in setuptools 82.0.1 | Change build-backend to `setuptools.build_meta` | build-env-manifest: constraint must give the exact string `setuptools.build_meta` — a vague principle ("prefer stable API") does not override a strong training prior; for configuration facts (specific strings, binary names), the manifest must be prescriptive, not intent-level | Constraint was too vague — "prefer stable established API" is a principle; coder's training prior associates `setuptools.backends.legacy:build` with "explicit build backend declaration" and overrides a principle but cannot override an explicit fact |
| 18 | `REQUIRED_FEATURE_COLUMNS` includes `LEASE_KID` (index) and `source_file` (dropped by ingest) | KGS | Features | FEA-08 enumerated a hardcoded column list; `LEASE_KID` is the entity index after transform `set_index(drop=True)` — not a column; `source_file` is added by `read_raw_file` but dropped by `enforce_schema` (not in data dictionary) — never reaches features | Remove `LEASE_KID` and `source_file` from `REQUIRED_FEATURE_COLUMNS`; validate index name separately | task-writer.md: task specs must not re-derive or enumerate data contracts — they must cite the authoritative boundary doc by name; column schema claims must be derived from boundary contracts, not reasoned from assumptions | Task-writer re-derived the required column list by local reasoning (transform columns + feature columns) rather than reading boundary-transform-features.md; local reasoning got both the index and a dropped column wrong |
| 19 | `ingest_file` returns untyped empty DataFrame before `enforce_schema` — causes meta mismatch | KGS | Ingest | Fine-grained task decomposition (ING-02 read, ING-03 filter, ING-05 orchestrate) led to early returns in `ingest_file` before `enforce_schema`; first raw file was `.gitkeep` (zero bytes) → `read_raw_file` returned `pd.DataFrame()` → returned before schema enforcement → untyped meta → `dd.from_delayed` metadata mismatch on all columns | Remove early returns from `ingest_file`; `enforce_schema` must always run regardless of empty input | stage-manifest-ingest H2 extended: schema enforcement applies to all DataFrames regardless of row count; zero-row DataFrame with correct dtypes is a valid output; task-writer.md Task Decomposition Constraint: all return paths must satisfy the same output contract | Fine-grained decomposition created an orchestrator function where early returns bypassed schema enforcement; task-writer optimized each function in isolation without tracing that untyped empty returns break the meta contract for `dd.from_delayed` |
| 20 | `set_index("LEASE_KID", drop=False)` keeps LEASE_KID as both index and column — Parquet write fails | KGS | Transform | TRN-05 task spec prescribed `drop=False` to retain LEASE_KID as a column for downstream use by TRN-06 (well completeness checker); `to_parquet` fails with "cannot insert LEASE_KID, already exists" | Change `drop=False` to `drop=True` | stage-manifest-transform H4: `set_index` must be the last structural operation before writing — all operations referencing the entity column must complete before `set_index` is called | Task-writer wrote TRN-05 (indexer) before TRN-06 (completeness checker) and prescribed `drop=False` to preserve LEASE_KID access in TRN-06; task spec made an implementation decision (drop=False) that conflicted with Parquet write constraints rather than referencing the stage manifest |
| 21 | `pipeline.py` `_setup_logging` ignores `log_file` from config — logs not written to file | KGS | Pipeline | `_setup_logging` uses `basicConfig` with console handler only; `log_file` key from config.yaml is read but ignored; no `FileHandler` added; ADR-006 mandates dual-channel logging (console + file), config-driven | Add `FileHandler` to `_setup_logging` using `log_file` from config | ADR-006 (dual-channel logging, config-driven); task-writer.md: pipeline.py must be in scope for task-writer with explicit ADR-006 reference for logging setup | Task-writer wrote tasks only for 4 stage modules — no pipeline.py task was specified; coder wrote `_setup_logging` without a task spec and without consulting ADR-006; no mechanism claim trigger existed to surface the ADR |
| 22 | `_build_empty_frame(dtype_map)` used for Dask meta despite ADR-003 prohibition | KGS | Ingest | `dd.from_delayed` needs `meta=`; task spec (I-04) was silent on meta derivation; coder fell back to training prior — named helper function, no I/O, feels clean; ADR-003 lines 81–85 explicitly prohibit separate meta construction but coder read it once in pre-flight and task spec gave no signal to re-consult it | Replace `_build_empty_frame(dtype_map)` with `_parse_one(str(txt_files[0])).iloc[0:0]` | task-writer.md Task Description Constraint: silence on a governed mechanism is not neutrality — task spec must cite the governing ADR by name; affirmative citation obligation added | Task-writer was silent on meta in I-04 (correctly avoided prescribing HOW) but failed the affirmative obligation to cite ADR-003; silence created a decision vacuum; coder filled it with training prior; Step 4 trigger never fired because task spec made no mechanism claim |
| 23 | Dask scheduler not initialized when running individual stages | KGS | Pipeline | `init_scheduler` only called inside the `acquire` branch of the stage loop; `make ingest` bypasses acquire → scheduler never initialized → Dask falls back to default scheduler | Move `init_scheduler` call before the stage loop, conditioned on any Dask stage being present | pipeline_tasks.md P-03/P-04: task-writer prescribed "initialize Dask scheduler after acquire completes and before ingest begins" — an ordering prescription that belongs in build-env-manifest, not a task spec | Task-writer made an ordering/mechanism claim (after acquire, before ingest) that described HOW not WHAT; the correct description is WHAT: scheduler must be active before any Dask stage runs; prescription broke the individual-stage invocation case |
| 24 | `parse_production_date` uses `.map()` with nested functions on `MONTH-YEAR` | KGS | Transform | `df["MONTH-YEAR"].map(_is_summary)` on `pd.StringDtype()` column returns `string` dtype mask, not `bool`; `df[~mask]` performs column selection instead of row filtering → all columns dropped → `KeyError: 'MONTH-YEAR'` at line 68; also `.map()` is non-vectorized (row-by-row Python) and nested functions cause Dask pickle issues | Rewrite using `str.extract`, `pd.to_numeric`, `pd.to_datetime(errors='coerce')` — fully vectorized | ADR-001 vectorization constraint: tightened "last resort" clause — string column transformations must use vectorized str methods; `.map()` with Python functions on string columns is not a valid last resort | Task-writer was silent on vectorization for `parse_production_date`; no mechanism claim in task spec → Step 4 never fired → coder rationalized `.map()` as "last resort" case per ADR escape hatch; same silence-as-vacuum pattern as error 22 |
| 25 | `fill_date_gaps` dtype loss — categorical columns become string after gap row concat | KGS | Transform | Gap rows constructed as `{c: pd.NA for c in columns}` dicts → `pd.DataFrame(gap_rows)` infers all-object dtypes → `pd.concat` with categorical-typed original strips category dtype from `TWN_DIR`, `RANGE_DIR`, `PRODUCT` → Parquet write fails with Arrow schema mismatch | Restore original dtypes after concat: `result[col].astype(df.dtypes[col])` for all columns | coding-patterns.md: when new rows are constructed and concatenated with an existing DataFrame, original dtypes must be restored after concat | Task-writer was silent on dtype preservation through intermediate row construction; task spec said "insert zero-production rows" but cited no governing document for dtype invariants; coder made a locally correct dict-based construction without considering global dtype preservation |
| 26 | Makefile uses `python3.11` binary — fails if only `python3` or `python3.12` is in PATH | KGS | Build | Coder wrote `PYTHON := python3.11` in Makefile after seeing `requires-python = ">=3.11"` in pyproject.toml; derived a specific binary from a minimum-version constraint; machine has Python 3.12 but not a `python3.11` symlink | Change `PYTHON := python3.11` to `PYTHON := python3` | build-env-manifest: Makefile venv target must use `python3` (unversioned); `requires-python` in pyproject.toml defines the minimum — do not infer a specific binary name from it | Build-env-manifest silent on which Python binary the Makefile should use; coder made an unverifiable local inference (min version → specific binary); same pattern as Error 17 |

---

## Constraint Test Status

| # | Constraint added | Tested by agent run |
|---|---|---|
| 1 | dtypes: nullable=yes → pd.Int64Dtype() | ✅ COGCC run 2 |
| 2 | dask-parquet: repartition formula | ✅ COGCC run 2 |
| 3 | transform: set_index → repartition → sort | ✅ COGCC run 2 |
| 4 | dtypes: meta from function call | ✅ COGCC run 2 |
| 5 | vectorization + batch compute | ✅ COGCC run 2 |
| 6 | build-env: scheduler split | ✅ COGCC run 2 |
| 7 | dtypes: nullable columns absent → fill NA | ✅ KGS run 3 (eval passed) |
| 8 | dtypes: column name normalization | ✅ KGS run 3 (eval passed) |
| 9 | stage-manifest-ingest: dask.delayed per file, not Dask bag | ❌ not yet — KGS pipeline failed |
| 10 | ADR-003: task specs must not prescribe meta construction | ❌ not yet |
| 11 | stage-manifest-acquire: BS4 isinstance guard | ❌ not yet |
| 12 | build-env-manifest: pipeline target single invocation | ✅ KGS run 3 (Makefile fixed) |
| 13 | dtypes: float null sentinel is np.nan not pd.NA | ❌ not yet |
| 14 | tests: numpy scalar identity — use == not is | ❌ not yet |
| 15 | tests: pandas Series negation — use ~ not == False | ❌ not yet |
| 16 | tests: no unused variable assignments | ❌ not yet |
| 17 | build-env-manifest: backend must be primary public entry point — no internal/legacy submodule paths; verify importability (constraint tightened from vague principle to elimination rule) | ❌ not yet — constraint updated 2026-04-24 |
| 18 | task-writer.md: task specs must not re-derive or enumerate data contracts — cite boundary doc by name | ❌ not yet |
| 19 | stage-manifest-ingest H2 extended + Task Decomposition Constraint: all return paths satisfy same output contract | ❌ not yet |
| 20 | stage-manifest-transform H4: set_index last before write | ❌ not yet |
| 21 | ADR-006 + pipeline.py in task-writer scope | ❌ not yet |
| 22 | task-writer.md: affirmative citation obligation — silence on governed mechanism is not neutrality | ❌ not yet |
| 23 | pipeline_tasks.md: scheduler init must be conditioned on Dask stage presence, not acquire branch | ❌ not yet |
| 24 | ADR-001: `.map()` with Python functions on string columns is not a valid last resort | ❌ not yet |
| 25 | coding-patterns.md: restore original dtypes after concat when constructing new rows | ❌ not yet |
| 26 | build-env-manifest: Makefile venv target must use unversioned `python3` — do not infer binary name from `requires-python` | ❌ not yet — constraint added 2026-04-24 |

---

## Common Threads

1. **Task isolation** — coder implements each task correctly in isolation but doesn't reason about cross-stage effects (partition count propagation, shuffle side effects, scheduler overhead). Errors 2, 3, 6.

2. **Correctness without scale** — code is functionally correct on small data but breaks at scale. No performance requirements in task specs until we added them. Error 5.

3. **Schema enforcement without nuance** — coder applies schema rules strictly but misses distinctions the data dictionary encodes (nullable vs non-nullable, absent vs null). Task spec language was ambiguous. Errors 1, 7, 8.

4. **Manual meta replication** — whenever meta is built by hand rather than derived from the function, it diverges. Errors 4, 10.

5. **Mechanism prescribed instead of intent** — task specs prescribe specific APIs/mechanisms (Dask bag, explicit meta construction loop) rather than describing what to achieve. Coder follows the prescribed mechanism literally even when it's wrong. Errors 9, 10, 12.

6. **Task spec overrides ADR** — when a task spec re-states or elaborates an ADR constraint in more specific terms, it creates a contradiction. The coder follows the more specific instruction (task spec) over the more general (ADR). ADR loses. Errors 10, 12.

7. **Type-safety blind spots on third-party types** — BeautifulSoup NavigableString/Tag union is a recurring mypy failure; coder reaches for `type: ignore` rather than type-safe guards. Requires multiple eval loops to resolve. Error 11.

8. **Local optimization without global data-flow tracing** — task-writer reasons about each task in isolation ("what should this function validate?") rather than tracing what data actually flows into it from upstream. This produces two simultaneous failure modes: over-specification (enumerating column lists from first principles instead of reading the boundary contract) and under-thoroughness (missing that upstream decisions like `drop=True` or `enforce_schema` dropping non-dictionary columns affect what columns exist). The task-writer is eager to be concrete and complete within a task, but doesn't simulate the full pipeline data flow before making schema claims. Error 18.

9. **The task-writer sweet spot — between over-specification and silence** — there is a failure mode on each side of the correct operating zone. Over-specification (pseudo-code, step sequences, specific API calls) creates a second source of truth that overrides ADRs and prescribes incorrect mechanisms. Under-specification (correct on WHAT, silent on which ADRs apply) creates decision vacuums the coder fills with training priors, bypassing authoritative documents. The sweet spot: task spec as a contract document — function purpose, inputs, outputs, test cases, plus an affirmative citation of the governing document for every design decision the coder will face. The key capability: task-writer must anticipate what design decisions the coder will encounter when implementing a function, and cite the governing document for each — without prescribing the implementation. Errors 22, 23, 24, 25.

10. **Configuration facts require elimination rules, not intent principles** — when a coder must write a value verbatim into a config file (build backend string, Python binary name, module path), a principle ("prefer the stable API") is non-deterministic. The coder resolves the principle via training prior, which can be wrong and is pipeline-specific. The fix is not to hard-code the exact string (maintainability burden) but to give an **elimination rule**: describe what the wrong answer looks like (internal submodule paths, names containing `legacy` or `backends`; versioned binary names derived from `requires-python`) so the coder can reason to the right answer rather than guess. Errors 17, 26.

---

## Error Metrics

Tracks recurrence class, first run, context file modified, and approximate word count added per fix.
Context-bit counts for errors 1–21 are estimates (retroactive — no per-commit word tracking at the time). Counts from error 22 onward are logged at time of fix.

| # | Class | Recurs as | First run | Context file(s) modified | Words added (est.) |
|---|---|---|---|---|---|
| 1 | new | — | COGCC-1 | ADRs.md (dtype nullable mapping) | ~40 |
| 2 | new | — | COGCC-1 | ADRs.md (ADR-004, repartition formula) | ~50 |
| 3 | new | — | COGCC-1 | stage-manifest-transform.md (set_index→repartition→sort) | ~60 |
| 4 | new | 10, 22 | COGCC-1 | ADRs.md (ADR-003, meta from function call) | ~80 |
| 5 | new | — | COGCC-1 | ADRs.md (ADR-001/002, vectorization + batch compute) | ~60 |
| 6 | new | — | COGCC-1 | build-env-manifest.md (scheduler split) | ~70 |
| 7 | new | — | KGS-1 | stage-manifest-ingest.md (nullable absent → fill NA) | ~50 |
| 8 | new | — | KGS-1 | stage-manifest-ingest.md (column name normalization) | ~60 |
| 9 | new | — | KGS-4 | stage-manifest-ingest.md (H4, dask.delayed per file) | ~80 |
| 10 | recurring (≡ #4) | 22 | KGS-4 | ADRs.md (ADR-003 strengthened) | ~60 |
| 11 | new | — | KGS-4 | stage-manifest-acquire.md (H3, BS4 isinstance guard) | ~70 |
| 12 | new | — | KGS-1 | build-env-manifest.md (pipeline target single invocation) | ~60 |
| 13 | new | — | KGS-4 | ADRs.md (ADR-003, float null sentinel = np.nan) | ~40 |
| 14 | new | — | KGS-4 | ADRs.md (test assertions: == not is for numpy scalars) | ~30 |
| 15 | new | — | KGS-4 | ADRs.md (Series negation: ~ not == False) | ~30 |
| 16 | new | — | KGS-4 | task-writer.md (no unused variable assignments in tests) | ~20 |
| 17 | new → recurred KGS-8 | 26 | KGS-4 | build-env-manifest.md (backend elimination rule) | ~80 |
| 18 | new | — | KGS-7 | task-writer.md (task specs must cite boundary docs, not re-derive) | ~90 |
| 19 | new | — | KGS-7 | stage-manifest-ingest.md (H2 extended) + task-writer.md | ~100 |
| 20 | new | — | KGS-7 | stage-manifest-transform.md (H4, set_index last before write) | ~70 |
| 21 | new | — | KGS-7 | pipeline_tasks.md (P2, ADR-006 dual-channel reference) | ~50 |
| 22 | recurring (≡ #10) | — | KGS-8 | task-writer.md (affirmative citation obligation) | 127 |
| 23 | new | — | KGS-8 | pipeline_tasks.md (P3/P4 scheduler init ordering) | ~60 |
| 24 | new | — | KGS-8 | ADRs.md (ADR-001, .map() on string cols not a valid last resort) | ~60 |
| 25 | new | — | KGS-8 | coding-patterns.md (restore dtypes after concat) | ~50 |
| 26 | recurring (≡ #17) | — | KGS-8 | build-env-manifest.md (python3 unversioned binary) | 49 |

**Cumulative context words added (estimated):** ~1,546  
**Exact counts available from:** error 22 onward

---

## Per-Run Log

Tracks errors surfaced per run. "New" = first occurrence of this error class. "Recurring" = error class previously seen and supposedly fixed.
Eval loop counts before run 8 are not available (not logged by evaluator at that time).

| Run | Pipeline | Date | Eval loops | New errors surfaced | Recurring | Notes |
|---|---|---|---|---|---|---|
| COGCC-1 | COGCC | unknown | ? | 1, 2, 3, 4, 5, 6 | 0 | First COGCC attempt |
| COGCC-2 | COGCC | unknown | ? | 0 | 0 | All 6 constraints passed |
| KGS-1 | KGS | unknown | ? | 7, 8, 12 | 0 | First KGS attempt; these 3 fixed by run 3 |
| KGS-2 | KGS | unknown | ? | — | 0 | Intermediate; no new error classes documented |
| KGS-3 | KGS | unknown | ? | 0 | 0 | Errors 7, 8, 12 constraints validated |
| KGS-4 | KGS | unknown | ? | 9, 10, 11, 13, 14, 15, 16, 17 | 0 | First full build attempt; setuptools error here |
| KGS-5 | KGS | unknown | ? | — | 0 | Intermediate; no new error classes documented |
| KGS-6 | KGS | unknown | ? | — | 0 | Intermediate |
| KGS-7 | KGS | unknown | ? | 18, 19, 20, 21 | 0 | Pre-Opus task-writer |
| KGS-8 | KGS | 2026-04-23 | 7 | 22, 23, 24, 25, 26 | 17 | Opus task-writer; first run with integration tests |

**Recurrence rate to date:** 2 recurrence events (errors 10, 22 as ≡ #4 class; error 17 returning in run 8) out of 26 total error instances = ~12% recurrence rate by error count.  
**Recurrence rate by run:** 1 run (KGS-8) had a recurring error out of 10 runs = 10% of runs had at least one recurrence.

---

## Overfitting Problem and Second Context Refactoring

### The Overfitting Cycle

Testing alternates between two pipelines (COGCC and KGS). Each test surfaces errors. Fixes are written into context files (task-writer.md, ADRs, stage manifests). But fixes tend to be too specific to the pipeline currently under test:

- Fix COGCC-specific errors → constraints encoded in context files are COGCC-shaped
- Test KGS → new errors appear, some caused by COGCC-specific constraints that don't generalize
- Fix KGS-specific errors → constraints are now KGS-shaped in other places
- Test COGCC → regression in areas where KGS fixes conflict with COGCC behavior
- Cycle repeats

This is overfitting to the most-recently-tested pipeline. Each iteration makes the context more complex and more contradictory, without improving generalization.

### What Global Minima Looks Like

A constraint that prevents an error in BOTH pipelines without referencing either pipeline's specific data, column names, or file structure. Intent-level, not example-level. It describes *why* something must be done, not *what specific thing* to do.

Example — current (overfitted): "Dask bag partitions compute to lists" (specific to the KGS bag mistake)
Example — global: "Parallelization of per-file reads must produce one delayed DataFrame per file — the mechanism must guarantee each delayed unit computes to a DataFrame, not a collection"

### Second Context Refactoring Goals

1. **ADRs own all constraints** — no constraint should live only in a task spec. Every constraint must be traceable to an ADR or stage manifest. Task specs reference; they do not define.

2. **Task specs describe intent only** — function signatures, what the function must achieve, test cases. No prescribed Dask APIs, no prescribed meta construction approach, no prescribed loop order. If a task spec prescribes a mechanism, that mechanism belongs in a stage manifest instead.

3. **Stage manifests own stage-specific patterns** — the correct Dask parallelization pattern for ingest (dask.delayed per file) belongs in stage-manifest-ingest.md, not in a task spec. Stage manifests are read before any task is written and before any task is implemented.

4. **When ADR and task spec conflict, ADR wins** — this must be stated explicitly in coder-advanced.md pre-flight. Currently the coder follows the more specific instruction (task spec) without checking for ADR conflicts.

5. **Constraints must be tested against both pipelines before being considered stable** — a constraint is not validated until it has been exercised in a successful agent run on both COGCC and KGS without regression in the other.