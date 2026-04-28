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
| 28 | task-writer invented index page scraping for acquire URL discovery | COGCC | Acquire | `acquire_tasks.md` prescribed `discover_annual_urls(index_url)` — fetches an HTML index page to discover ZIP URLs; index page (`ecmc.state.co.us/.../index.html`) does not exist → 404 at runtime; prior Opus run on the same spec produced direct URL construction and worked correctly | Not yet fixed in task spec; workaround: delete tasks and re-run task-writer, or manually correct acquire_tasks.md to use direct URL construction | task-writer-cogcc.md: add explicit prohibition "URL construction must use the `{year}_prod_reports.zip` template directly — do not fetch or scrape an index page to discover URLs" | task-writer added complexity that wasn't asked for — not misinterpreting an unclear spec. Spec was unambiguous (URL templates fully specified). Suspected trigger: BeautifulSoup listed in build-env-manifest.md as an acquire dependency; Opus may have looked for a use for it. Same model, same documents, different output across runs — non-determinism in task-writer is a reliability risk. |
| 27 | Duplicate `(well_id, production_date)` rows survive transform dedup — `cum_oil` non-monotonic in features | COGCC | Transform | COGCC raw data contains "Revised" reports — a revised monthly submission for the same well/month; 276+ wells per partition have two rows for the same date after transform; `cum_oil` cumsum accumulates over both rows → steps backward (e.g., 1237 → 1230 for same date) → non-monotonic per well; integration tests did not catch this (no cum_oil monotonicity check); pipeline passed eval | Not yet fixed; dedup must key on `(well_id, production_date)` after `set_index`, keeping the most recent `Revised` record | stage-manifest-transform: dedup must be keyed on the entity index + date column after `set_index`; when multiple rows exist for the same (entity, date), the Revised flag must determine which row is kept (latest Revised=True preferred, else latest by AcceptedDate) | Transform dedup was implemented but not keyed correctly for COGCC's Revised report pattern; task spec did not describe the dedup key or tie-breaking rule; no integration test asserts cum_oil monotonicity |
| 30 | Dask-level column assignment on duplicate-indexed ddf — `ddf["col"] = ddf.groupby(...).cumsum()` fails at compute | COGCC | Features | `add_cumulative_features` assigns groupby results at the Dask Series level; Dask internally uses assign which reindexes against the ddf; duplicate `well_id` index triggers "cannot reindex on an axis with duplicate labels" | Use `map_partitions` with explicit meta for all grouped transformations on a duplicate-indexed ddf — never assign groupby results directly at the Dask level | stage-manifest-features: any grouped transformation on an entity-indexed ddf must use map_partitions; Dask-level column assignment via `ddf["col"] = series` is unsafe when the index has duplicate labels | Gemini-flash generated Dask-level assignments instead of map_partitions; same root failure class as rolling reset_index bug (Error 29) — both are Dask-level operations that fail on duplicate index |
| 31 | `decline_rate` all null — `pd.Series` from numpy array loses index alignment with indexed DataFrame | KGS | Features | `add_decline_rate` computes rate via `np.where(...)` producing a numpy array (no index); wraps in `pd.Series(pd.array(rate, dtype="float64"))` with default RangeIndex(0…n-1); `df["decline_rate"] = rate_series` aligns by index → LEASE_KID index vs RangeIndex → all NaN on every row; not caught by eval unit tests (test fixtures used RangeIndex DataFrames) | Pass `index=df.index` to `pd.Series(...)` constructor | coding-patterns.md: when constructing `pd.Series` from a numpy array (e.g., `np.where` output) to assign into a DataFrame with a non-default index, always pass `index=df.index` — default RangeIndex causes silent all-NaN via pandas index alignment | Coder produced index-less numpy array via `np.where`, wrapped in `pd.array` correctly, then failed to restore the index in the `pd.Series` constructor; all other feature functions used `groupby/transform` or `groupby/cumsum` (inherently index-preserving) so no misaligned pattern was visible as a contrast; unit tests passed because test fixtures used RangeIndex DataFrames — the bug is only visible when the DataFrame has a non-default index |
| 29 | `drop_duplicates()` with no key → duplicate `(well_id, production_date)` survive → rolling `reset_index` crash in features | COGCC | Transform / Features | `transform.drop_duplicates()` deduplicates on all columns; COGCC "Revised" reports have same `(well_id, production_date)` but different production values → survive as distinct rows; after `set_index("well_id")`, duplicate `(well_id, production_date)` pairs in index; `add_rolling_and_lag_features` does `roller.mean().reset_index(level=0, drop=True)` → resulting Series has duplicate labels → `ValueError: cannot reindex on an axis with duplicate labels` | Fix `drop_duplicates` in transform.py to key on `(well_id, production_date)` subset with tie-break by `AcceptedDate` descending (keep first after sort) | stage-manifest-transform: `drop_duplicates` must specify `subset=[entity_index, date_col]`; tie-breaking rule: sort by `AcceptedDate` descending before dedup, keep first; `drop_duplicates()` with no subset is never correct for time-series pipeline data with revision patterns | Same root cause as Error 27 (Revised reports not deduped on key) but manifests as a hard crash in features rolling computation rather than silent non-monotonic output; `drop_duplicates()` with no key is a recurring anti-pattern — dedup without a key is only safe when rows are truly identical on all columns, which is never the case for revised production reports |

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
| 9 | stage-manifest-ingest: dask.delayed per file, not Dask bag | ⏳ added 2026-04-27; untested |
| 10 | ADR-003: task specs must not prescribe meta construction | ❌ not yet |
| 11 | stage-manifest-acquire: BS4 isinstance guard | ❌ not yet |
| 12 | build-env-manifest: pipeline target single invocation | ✅ KGS run 3 (Makefile fixed) |
| 13 | dtypes: float null sentinel is np.nan not pd.NA | ⏳ added 2026-04-27 to ADR-003; untested |
| 14 | tests: numpy scalar identity — use == not is | ⏳ added 2026-04-27 to coding-patterns.md; untested |
| 15 | tests: pandas Series negation — use ~ not == False | ⏳ added 2026-04-27 to coding-patterns.md; untested |
| 16 | tests: no unused variable assignments | ⏳ added 2026-04-27 to coding-patterns.md; untested |
| 17 | build-env-manifest: backend must be primary public entry point — no internal/legacy submodule paths; verify importability (constraint tightened from vague principle to elimination rule) | ✅ COGCC-4 (no Install failure — constraint held) |
| 18 | task-writer.md: task specs must not re-derive or enumerate data contracts — cite boundary doc by name | ❌ not yet |
| 19 | stage-manifest-ingest H2 extended + Task Decomposition Constraint: all return paths satisfy same output contract | ❌ not yet |
| 20 | stage-manifest-transform H4: set_index last before write | ❌ not yet |
| 21 | ADR-006 + pipeline.py in task-writer scope | ❌ not yet |
| 22 | task-writer.md: affirmative citation obligation — silence on governed mechanism is not neutrality | ❌ not yet |
| 23 | build-env-manifest: scheduler init before any Dask stage, not inside acquire branch | ⏳ added 2026-04-27; untested |
| 24 | ADR-002: `.map()` with Python functions on string columns is not a valid last resort | ⏳ added 2026-04-27; untested |
| 25 | coding-patterns.md: restore original dtypes after concat when constructing new rows | ❌ not yet |
| 26 | build-env-manifest: Makefile venv target must use unversioned `python3` — do not infer binary name from `requires-python` | ✅ COGCC-4 (no Install failure — constraint held) |
| 27 | stage-manifest-transform H5: dedup must key on (entity index, date) after set_index; bare drop_duplicates() with no subset is never correct | ⏳ added 2026-04-27; untested |
| 28 | task-writer.md: URL construction + dependency scope constraints — no discovery step when URLs are specified; library presence ≠ requirement | ⏳ added 2026-04-27; untested |
| 29 | coder-basic.md: ADR authority rule — flag BLOCKER if task spec contradicts ADR; do not implement the task spec | ⏳ added 2026-04-27; untested |
| 30 | agent_docs/model-behavior-constraints.md: NEW — 9-pattern anticipation guide for orchestrator + task-writer; prospective failure mode coverage | ⏳ added 2026-04-27; untested |
| 31 | coding-patterns.md: `pd.Series` from numpy array inside an indexed DataFrame must pass `index=df.index` | ❌ not yet |

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
| 27 | new | — | COGCC-4 (output review) | stage-manifest-transform.md (dedup key + tie-break rule) | — |
| 31 | new | — | KGS pipeline test (post-eval, 2026-04-28) | coding-patterns.md | ~50 |

**Cumulative context words added (estimated):** ~1,596  
**Exact counts available from:** error 22 onward

---

## Per-Run Log

Tracks errors surfaced per run. Eval loop data sourced from `eval_results.md` git history in the kgs and cogcc repos (both separate from dapi_poc). KGS runs before 2026-04-01 predate evaluator file logging and have no eval data.

Error-to-run mapping for early runs is approximate — test names changed across versions and don't map cleanly to error table numbers.

| Run | Pipeline | Date | Eval loops (to first pass) | Eval duration | Main test failures | Error #s (approx) | Tokens / Cost |
|---|---|---|---|---|---|---|---|
| COGCC-1 | COGCC | 2026-04-05 | 5 | 46m 21s | features: cumulative monotonic, schema validation/logging | est. 2, 4, 5 | — |
| COGCC-2 | COGCC | 2026-04-09 | 4 | 46m 23s | ingest: dtypes, missing col raises; transform: production_date dtype, well_status cast | est. 1, 3, 7 | — |
| COGCC-3 | COGCC | 2026-04-16 | 3 | 1h 3m 44s | features: rolling partial window; ingest: missing nullable col, schema key count; transform: dtype, clean_volumes, TR-12 | est. 1, 2, 7, 8 | — |
| KGS pre-log | KGS | 2026-03-21 to 2026-03-31 | ? | ? | no eval_results.md (pre-evaluator logging) | 7, 8, 12 (est.) | — |
| KGS-A | KGS | 2026-04-01 | 6 | 29m 54s | features: cumulative/schema/categoricals; transform: duplicates | early feature/transform (est. 9, 13) | — |
| KGS-B | KGS | 2026-04-16 | 3 | 33m 10s | acquire: idempotency; ingest: dtype mapping, dtype_validation | est. 6, 7 | — |
| KGS-C | KGS | 2026-04-17 | 5 | 38m 13s | ingest: absent nullable col, categorical→NA, year filter, url col drop; transform: physical bounds | est. 7, 8, 10 | — |
| KGS-D | KGS | 2026-04-20 | 3 | 17m 18s | ingest: enforce_schema drops extra col, schema key count; transform: parse_production_date malformed | est. 8, 17, 24 | — |
| KGS-E | KGS | 2026-04-23 | 7 | 16m 41s | features: cumulative/decline/rolling; ingest: empty file returns; pipeline: logging handlers, stage ordering | est. 18, 19, 21, 22, 23 | — |
| KGS-F (Opus) | KGS | 2026-04-23 | 7 | 27m 42s | see loop detail below | 22–26, recurring 17 | 4.6M / $7.10 (91% cache) |
| COGCC-4 | COGCC | 2026-04-24 | 12 | 54m 17s | see loop detail below | recurring 10/22/13; type errors in ingest/features/transform | 14.1M / $11.60 (94% cache) |
| COGCC-5 | COGCC | 2026-04-27 | 4 | 23m 23s | see loop detail below | recurring 13 (pd.NA/float); CategoricalDtype null values → Arrow cast failure | — |
| KGS-G | KGS | 2026-04-27 | 6 (2 false) | 37m active / 3h total | see loop detail below | recurring 17 (build backend); BS4 NavigableString (Error 11 class); 2 false loops (cancel/resume) | — |

**Recurrence rate to date:** 3 recurrence events (errors 10, 22 as ≡ #4 class; error 17 returning in KGS-F; error 13 float/NA regression in COGCC-4 loop 8) out of 26 total error instances = ~12% recurrence rate by error count.  
**Recurrence rate by run:** 2 runs (KGS-F, COGCC-4) had recurring errors out of 10 logged runs (4 COGCC + 6 KGS) = 20% of runs had at least one recurrence.  
**6-loop limit violation:** COGCC-4 ran 12 loops — orchestrator did not stop at 6 as mandated by the rules. Needs investigation.

**Eval duration summary (all logged runs):**

| Run | Loops | Duration | Avg per loop |
|---|---|---|---|
| COGCC-1 | 5 | 46m 21s | 9m 17s |
| COGCC-2 | 4 | 46m 23s | 11m 36s |
| COGCC-3 | 3 | 1h 3m 44s | 21m 15s |
| KGS-A | 6 | 29m 54s | 4m 59s |
| KGS-B | 3 | 33m 10s | 11m 3s |
| KGS-C | 5 | 38m 13s | 7m 38s |
| KGS-D | 3 | 17m 18s | 5m 46s |
| KGS-E | 7 | 16m 41s | 2m 23s |
| KGS-F | 7 | 27m 42s | 3m 58s |
| COGCC-4 | 12 | 54m 17s | 4m 31s |
| COGCC-5 | 4 | 23m 23s | 5m 51s |
| KGS-G | 6 | 37m active | 7m 28s (active loops) |

### COGCC-1 Eval Loop Detail (2026-04-05)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 12:56:36 | ❌ | type check + `test_apply_well_features_parallel_cum_oil_monotonic`, `test_validate_features_schema_missing_column`, `test_run_features_logs_schema_error_without_raising` | 22m 49s |
| 2 | 13:19:25 | ❌ | `test_apply_well_features_parallel_cum_oil_monotonic`, `test_validate_features_schema_missing_column`, `test_run_features_logs_schema_error_without_raising` | 9m 6s |
| 3 | 13:28:31 | ❌ | `test_apply_well_features_parallel_cum_oil_monotonic`, `test_validate_features_schema_missing_column`, `test_run_features_logs_schema_error_without_raising` | 7m 16s |
| 4 | 13:35:47 | ❌ | `test_run_features_logs_schema_error_without_raising` | 7m 10s |
| 5 | 13:42:57 | ✅ | — | — |

### COGCC-2 Eval Loop Detail (2026-04-09)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 05:13:25 | ❌ | linting + type check (test names not captured in eval_results.md for this loop) | 22m 41s |
| 2 | 05:36:06 | ❌ | type check + `test_read_raw_file_dtypes`, `test_read_raw_file_missing_column_raises`, `test_build_production_date_dtype`, `test_cast_well_status_valid_values`, `test_transform_partition_production_date_dtype` | 16m 16s |
| 3 | 05:52:22 | ❌ | type check only (no unit test failures) | 7m 26s |
| 4 | 05:59:48 | ✅ | — | — |

### COGCC-3 Eval Loop Detail (2026-04-16)

4 entries in eval_results.md; first pass at loop 3. Loop 4 (14:32:43 ✅) is a separate re-run after commit, not part of the eval sequence.

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 11:35:44 | ❌ | linting + type check + `test_rolling_6month_partial_window`, `test_load_data_dictionary_returns_33_keys`, `test_enforce_schema_missing_nullable_column`, `test_add_derived_columns_production_date_dtype`, `test_add_derived_columns_well_id_dtype`, `test_clean_volumes_oil_unit_flag_high`, `test_clean_volumes_oil_unit_flag_normal`, `test_tr12_cleaning_validation` | 49m 35s |
| 2 | 12:25:19 | ❌ | linting only (no unit test failures) | 14m 9s |
| 3 | 12:39:28 | ✅ | — | — |

**Observation:** Loop 1→2 gap = 49m 35s — longest single coder iteration across all runs (both pipelines). This was likely a large structural rewrite of multiple stages simultaneously.

### KGS-A Eval Loop Detail (2026-04-01)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 10:46:09 | ❌ | linting + type check + unit (test names not captured for this loop) | 7m 53s |
| 2 | 10:54:02 | ❌ | type check + `test_compute_cumulative_shutin_flat`, `test_encode_categoricals_product_two_values`, `test_encode_categoricals_county_int_dtype`, `test_encode_categoricals_original_col_retained`, `test_encode_categoricals_unseen_value`, `test_run_features_returns_dask_df`, `test_run_features_all_schema_columns`, `test_run_features_no_negative_oil_bbl`, `test_run_features_cum_oil_monotonic`, `test_run_features_parquet_readable`, `test_run_features_schema_stability_across_partitions`, `test_run_features_output_file_count`, `test_feature_column_presence`, `test_cumulative_monotonicity`, `test_schema_stability_across_partitions`, `test_lazy_evaluation`, `test_remove_duplicates_removes_one` | 6m 31s |
| 3 | 11:00:33 | ❌ | type check + unit (test names not captured) | 4m 44s |
| 4 | 11:05:17 | ❌ | type check + `test_run_features_all_schema_columns`, `test_run_features_cum_oil_monotonic`, `test_feature_column_presence`, `test_cumulative_monotonicity`, `test_remove_duplicates_removes_one` | 6m 43s |
| 5 | 11:12:00 | ❌ | type check only (no unit test failures) | 4m 3s |
| 6 | 11:16:03 | ✅ | — | — |

### KGS-B Eval Loop Detail (2026-04-16)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 18:26:55 | ❌ | type check + `TestDownloadLeaseFile::test_idempotency_skips_existing`, `TestReadRawFile::test_correct_dtypes_and_source_file`, `TestRunIngest::test_dtype_validation` | 26m 13s |
| 2 | 18:53:08 | ❌ | `TestDownloadLeaseFile::test_idempotency_skips_existing`, `TestResolvePandasDtype::test_int_not_nullable` | 6m 57s |
| 3 | 19:00:05 | ✅ | — | — |

**Observation:** Loop 1 → 2 gap = 26m — longest single coder iteration across all runs. Likely a large structural rewrite.

### KGS-C Eval Loop Detail (2026-04-17)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 00:03:16 | ❌ | linting + type check + `test_read_raw_file_absent_nullable_column`, `test_read_raw_file_year_filter`, `test_read_raw_file_non_numeric_year_dropped`, `test_read_raw_file_invalid_categorical_becomes_na`, `test_read_raw_file_url_column_dropped`, `test_validate_physical_bounds_oil_flag_over_50000`, `test_validate_physical_bounds_gas_no_flag` | 18m 59s |
| 2 | 00:22:15 | ❌ | linting + type check + `test_read_raw_file_url_column_dropped` | 9m 8s |
| 3 | 00:31:23 | ❌ | type check only | 5m 46s |
| 4 | 00:37:09 | ❌ | type check only | 4m 20s |
| 5 | 00:41:29 | ✅ | — | — |

### KGS-D Eval Loop Detail (2026-04-20)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 00:30:21 | ❌ | type check + `test_enforce_schema_drops_extra_column`, `test_parse_production_date_malformed_gives_nat` | 12m 14s |
| 2 | 00:42:35 | ❌ | `test_load_schema_returns_21_keys` | 5m 4s |
| 3 | 00:47:39 | ✅ | — | — |

### KGS-E Eval Loop Detail (2026-04-23 AM)

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 10:27:05 | ❌ | linting + type check + `TestAddCumulativeProduction::test_monotonically_nondecreasing`, `test_shut_in_month_flat_cumulative`, `test_first_month_zero_gives_zero_cumulative`, `test_resumes_after_shut_in`, `TestAddDeclineRate::test_clipped_below_minus_one`, `test_clipped_above_ten`, `test_within_bounds_passes_through`, `test_two_consecutive_zeros_no_extreme`, `TestAddRollingFeatures::test_lag_1_equals_prior_month`, `TestParseRawFile::test_empty_file_returns_empty_dataframe`, `TestSetupLogging::test_adds_stream_and_file_handler`, `TestMain::test_only_acquire_called_when_stage_is_acquire`, `test_setup_logging_called_first`, `test_exception_stops_downstream_stages` | 7m 22s |
| 2 | 10:34:27 | ❌ | type check + `TestAddDeclineRate::test_clipped_below_minus_one`, `test_clipped_above_ten`, `test_within_bounds_passes_through`, `test_two_consecutive_zeros_no_extreme`, `TestSetupLogging::test_adds_stream_and_file_handler` | 3m 2s |
| 3 | 10:37:29 | ❌ | `TestAddDeclineRate::test_clipped_below_minus_one`, `TestSetupLogging::test_adds_stream_and_file_handler` | 1m 56s |
| 4 | 10:39:25 | ❌ | `TestSetupLogging::test_adds_stream_and_file_handler` | 1m 46s |
| 5 | 10:41:11 | ❌ | `TestSetupLogging::test_adds_stream_and_file_handler` | 1m 19s |
| 6 | 10:42:30 | ❌ | `TestSetupLogging::test_adds_stream_and_file_handler` | 1m 16s |
| 7 | 10:43:46 | ✅ | — | — |

**Observation:** Loops 3–7 all under 2 min — rapid iteration on small incremental fixes after the major fix in loop 1→2. `test_adds_stream_and_file_handler` stuck for loops 4–6 (3 consecutive loops on a single test).

### KGS-F Eval Loop Detail (2026-04-23 PM, Opus task-writer)

4.6M tokens, $7.10 (4.2M input from cache = 91% cache hit rate). Total eval window: 15:11:59 → 15:39:41 (27m 42s).

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 15:11:59 | ❌ | linting (F841 x2) + type check (15 errors) + `test_resolve_download_url_http_error_returns_none`, `test_download_file_non_utf8_no_file_left`, `test_f2_cumulative_sums_known_values`, `test_f2_cum_flat_across_zero_production`, `test_f2_cum_stays_zero_when_not_started`, `test_f2_gor_zero_oil_positive_gas`, `test_f2_gor_both_zero`, `test_f2_gor_gas_zero_oil_positive`, `test_f2_water_cut_zero_water`, `test_f2_water_cut_all_water`, `test_f2_decline_rate_clip_lower`, `test_f2_decline_rate_clip_upper`, `test_f2_decline_rate_within_bounds`, `test_f2_decline_rate_shutin_then_resume_clipped`, `test_f5_complete_column_set_tr19`, `test_f5_tr14_consistent_schema_across_partitions`, `test_meta_derivation_matches_live_output` + integration: `test_f5_tr26_integration`, `test_e2e_ingest_transform_features`, `test_transform_tr25_integration` | 9m 19s |
| 2 | 15:21:18 | ❌ | `test_f5_complete_column_set_tr19`, `test_f5_tr14_consistent_schema_across_partitions` + integration: `test_f5_tr26_integration`, `test_e2e_ingest_transform_features`, `test_transform_tr25_integration` | 4m 6s |
| 3 | 15:25:24 | ❌ | Same 5 as loop 2 — no progress | 4m 35s |
| 4 | 15:29:59 | ❌ | Same 5 as loop 2 — no progress | 3m 16s |
| 5 | 15:33:15 | ❌ | Same 5 as loop 2 — no progress | 3m 10s |
| 6 | 15:36:25 | ❌ | Integration: `test_e2e_ingest_transform_features`, `test_transform_tr25_integration` (f5 unit tests now passing) | 3m 16s |
| 7 | 15:39:41 | ✅ | — | — |

**Observation:** Loops 2–5 = zero progress on same 5 failures for ~15 min (stuck on features column schema + integration partition counts). Loop 1→2 was the high-value fix (cleared 15 failures). KGS-E had the same 7-loop count but resolved in 16m 41s vs 27m 42s here — integration tests added in KGS-F increased per-loop cost.

### COGCC-4 Eval Loop Detail (2026-04-24)

Total eval window: 05:52:17 → 06:46:34 (54m 17s). 12 loops — orchestrator 6-loop limit exceeded.

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 05:52:17 | ❌ | Linting, type check (transform x3, ingest x3, features x6 = 12 errors), unit (ingest x10, transform x4: null_entity + schema_stable + well_completeness + meta_matches), integration x4 | 7m 51s |
| 2 | 06:00:08 | ❌ | Type check (ingest x5, features x5), unit (ingest x4, transform x3: schema_stable + well_completeness + meta_matches), integration x4 | 9m 29s |
| 3 | 06:09:37 | ❌ | Type check (ingest x2, features x1), unit (transform x2: schema_stable + meta_matches) | 8m 25s |
| 4 | 06:18:02 | ❌ | Linting (F841 `original_cols` x2 in transform), unit (transform x2: schema_stable + meta_matches) | 5m 22s |
| 5 | 06:23:24 | ❌ | Unit (transform x2: schema_stable + meta_matches) | 4m 11s |
| 6 | 06:27:35 | ❌ | Unit (transform x1: meta_matches only) | 3m 24s |
| 7 | 06:30:59 | ❌ | REGRESSION: type check reintroduced (transform x2) + unit (meta_matches) | 4m 36s |
| 8 | 06:35:35 | ❌ | REGRESSION: 5 new clean_partition failures (`pd.NA` for float64 = Error 13 class) + meta_matches = 7 unit failures | 2m 24s |
| 9 | 06:37:59 | ❌ | Type check (transform x2) + unit (meta_matches: DaysProduced int64 vs float64) | 3m 40s |
| 10 | 06:41:39 | ❌ | Unit (meta_matches: OpNumber float64 vs string) | 2m 10s |
| 11 | 06:43:49 | ❌ | Unit (meta_matches: Revised bool vs string) | 2m 45s |
| 12 | 06:46:34 | ✅ | — | — |

**Key observations:**
- `test_transform_map_partitions_meta_matches_output` stuck in loops 2–11 (10 consecutive loops) — same ADR-003 meta derivation recurring pattern as KGS-F.
- Each loop 9–11 shows a different column dtype mismatch (DaysProduced, OpNumber, Revised) — coder is fixing one column per loop rather than deriving meta from the actual function output.
- Loop 8 regression: coder introduced `pd.NA` as null sentinel for float64 columns while fixing meta — triggers Error 13 class (`TypeError: float() argument must be a string or a real number, not 'NAType'`). Error 13 constraint (added for KGS) did not prevent this in COGCC-4.
- Loop 7 regression: type check reintroduced after being clean in loops 4–6. Coder over-corrected while fixing meta_matches.
- 12 loops: orchestrator ran 6 loops past its stated limit with no human escalation — rule not enforced.
- No Install failure: build backend (constraint 17) and Python binary (constraint 26) were correct in this run — both constraints held.

### COGCC-5 Eval Loop Detail (2026-04-27)

Total eval window: 12:59:18 → 13:22:41 (23m 23s). 4 loops.

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 12:59:18 | ❌ | Linting (F841 `schema` in test_transform.py) + type check + unit (19 failed: acquire x1, features cumulative x3, ingest dtype x8 including float null pd.NA and categorical, transform dedup x4) + integration (ArrowNotImplementedError: WellStatus CategoricalDtype values=null → Arrow cast fails; pipeline stage 'ingest' failed: bool-like values error) | 10m 28s |
| 2 | 13:09:46 | ❌ | Type check + unit (4: features cumulative x3 + ingest dtype spot check) + integration (1: test_download_file_real_download) | 9m 14s |
| 3 | 13:19:00 | ❌ | Type check + unit (same 4 as loop 2 — no progress) | 3m 41s |
| 4 | 13:22:41 | ✅ | — | — |

**Key observations:**
- Loop 1 integration failure: `WellStatus` CategoricalDtype with values=null — bare `CategoricalDtype()` in ingest maps each file's unique category set → Parquet merge fails with `ArrowNotImplementedError: Unsupported cast from large_string to null`. Same root cause as H5 fix applied to KGS (CategoricalDtype → StringDtype in ingest).
- Loop 3 = zero progress on same 4 failures as loop 2 (features cumulative + ingest dtype spot check — coder-basic hit its scope limit on these complex failures before coder-advanced resolved them in loop 4).
- Constraint 17 (build backend) and constraint 26 (Python binary) both held — no Install failure.

### KGS-G Eval Loop Detail (2026-04-27)

Total eval window: 19:17:33 → 22:20:31 (3h 3m including ~2.5h billing pause). Active eval (loops 1–5): 19:17:33 → 19:54:51 (37m 18s).

| Loop | Time | Status | Failures | Duration to next |
|---|---|---|---|---|
| 1 | 19:17:33 | ❌ | Install: build backend error — `setuptools.backends.legacy:build` not found (Error 17 recurring) | 3m 59s |
| 2 | 19:21:32 | ❌ | Linting (F841 x2: test_ingest, test_pipeline) + type check (5 errors: features.py NumpyExtensionArray.clip, acquire.py BS4 NavigableString, pipeline.py Callable type x3) + unit (20 failed) + integration | 16m 41s |
| 3 | 19:38:13 | ❌ | Linting (F841 x1: test_ingest) + type check (1: NumpyExtensionArray.clip in features.py:98) + unit (21 failed: decline_rate x6, apply_features x3, features x5, pipeline x1, transform x5) + integration | 7m 55s |
| 4 | 19:46:08 | ❌ | Integration: 0 tests selected — false loop (coder-advanced cancelled mid-fix; orchestrator resume-from-evaluator rule triggered eval without new code) | 8m 43s |
| 5 | 19:54:51 | ❌ | Integration: 0 tests selected — false loop (same) | ~2h 25m (API billing depleted; manual top-up + server restart) |
| 6 | 22:20:31 | ✅ | — | — |

**Key observations:**
- Loop 1: Error 17 recurring — constraint marked ✅ (held in COGCC-4) but failed here; constraint may need further hardening or KGS task-writer regeneration is needed to pick it up.
- Loop 2→3 gap = 16m 41s — multi-error fix covering linting, type check, and unit failures simultaneously.
- Loop 3 decline_rate failures: `NumpyExtensionArray.clip` type error prevented the clip-based fix from working cleanly; underlying all-null bug (Error 31: `pd.Series` without `index=df.index`) not caught by unit tests — unit fixtures used RangeIndex DataFrames.
- Loops 4–5: 2 wasted loops — `resume-from-evaluator` orchestrator rule triggered on a cancelled coder-advanced call; 0 tests selected because integration marker was misconfigured after mid-run state. Rule removed from orchestrator.md after this run.
- ~2.5h gap before loop 6: Anthropic API billing depleted during run; required manual balance top-up and LangGraph server restart.

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

### Prospective Layer: model-behavior-constraints.md (added 2026-04-27)

Where the second refactoring fixed the *authority hierarchy* (who wins when task spec and ADR conflict), a complementary document addresses the *timing problem*: by the time a recurring error surfaces in an eval loop, a full coder invocation has already been spent on it. `agent_docs/model-behavior-constraints.md` gives the orchestrator 9 failure patterns to scan for **before** delegating to task-writer — so preventive constraints can be added to the spec rather than discovered at eval time.

The 9 patterns (all derived from the error table): discovery injection, dependency activation, scope-to-full-pattern, prior-driven concretization, task decomposition gaps, meta construction, performance without scale, silent dtype loss, and test fixture mismatch. Each entry has a trigger condition (what in the spec signals risk) and a preventive measure (what constraint to add before the run).

This does not replace the authority hierarchy — it adds a pre-delegation scan layer on top of it. The document is read by the orchestrator before every task-writer delegation; it is not consumed by the coder.

The document was added after COGCC-4's 12-loop run exceeded the 6-loop limit — indicating that known recurring error classes were being re-encountered rather than anticipated. The prospective layer is the mechanism for breaking that cycle.