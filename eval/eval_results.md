# KGS Pipeline — LLM Judge Eval Results
*Generated: 2026-03-26 09:15*
*Judge: Groq / llama-3.3-70b-versatile*

## Summary

| File | domain_correctness_acquire | test_quality | pipeline_integrity_acquire |
|---||---||---||---|
| test_acquire.py | ✓ 0.80 | ✓ 0.80 | ✓ 0.80 |

| File | domain_correctness_ingest | test_quality | pipeline_integrity_ingest |
|---||---||---||---|
| test_ingest.py | ✓ 0.60 | ✓ 0.80 | ✓ 0.80 |

| File | domain_correctness_transform | test_quality | pipeline_integrity_transform |
|---||---||---||---|
| test_transform.py | ✓ 0.60 | ✓ 0.80 | ✓ 0.80 |

| File | domain_correctness_features | test_quality | pipeline_integrity_features |
|---||---||---||---|
| test_features.py | ✓ 0.80 | ✓ 0.80 | ✓ 0.80 |

---

## Detail

### test_acquire.py

**domain_correctness_acquire** — PASS (0.80)

> The test file includes tests for idempotency in the acquire step, verifying that running it twice on
> the same target directory does not duplicate files or corrupt existing ones, as seen in
> test_run_acquire_pipeline_idempotent and test_scrape_idempotency_skips_existing. It also checks for
> file integrity, ensuring downloaded files are not empty and contain at least one data row beyond the
> header, as demonstrated in tests like test_is_valid_raw_file_valid and
> test_is_valid_raw_file_zero_bytes. However, the test file does not explicitly verify that the number
> of downloaded files matches the number of leases or targets requested, which is a crucial aspect of
> file count reconciliation.

**test_quality** — PASS (0.80)

> The test suite covers various scenarios, including happy paths and edge cases, with a good mix of
> unit tests and integration tests. It also checks for idempotency and error propagation. However,
> some tests only check the return type or mock the entire function under test, which could be
> improved by testing the actual functionality. Additionally, there are no tests for invalid inputs or
> extreme values in some cases, which could lead to incomplete testing.

**pipeline_integrity_acquire** — PASS (0.80)

> The tests provided use mocking to avoid real network calls and verify the output directory structure
> after acquire, checking for the existence of expected subdirectories and files in the correct
> locations. However, some tests only check that a function returns without error, rather than
> verifying the filesystem state is correct.

### test_ingest.py

**domain_correctness_ingest** — PASS (0.60)

> The test file covers various aspects of the ingest pipeline, including discovering raw files,
> reading raw files, filtering monthly records, enriching with lease metadata, applying the interim
> schema, and writing interim parquet files. However, it does not explicitly test the distinction
> between zero production and missing data, and unit consistency is only partially addressed through
> the application of the interim schema. Date parsing is also not explicitly tested.

**test_quality** — PASS (0.80)

> The test suite covers various tasks and functions, including discover_raw_files, read_raw_files,
> filter_monthly_records, enrich_with_lease_metadata, apply_interim_schema, write_interim_parquet, and
> run_ingest_pipeline. It tests for different scenarios, such as handling empty directories,
> nonexistent files, and invalid data. However, some tests only check for the return type or the
> presence of certain columns, which may not be sufficient to ensure the correctness of the functions.
> Additionally, there are no tests for floating-point comparisons, which could lead to fragile tests.

**pipeline_integrity_ingest** — PASS (0.80)

> The tests verify the ingest output schema, check for Dask laziness, and test row count
> reconciliation. However, they do not thoroughly verify the ingest output schema's dtypes and do not
> test deduplication idempotence. Additionally, some tests read from disk, which may cause issues in
> CI.

### test_transform.py

**domain_correctness_transform** — PASS (0.60)

> The test file covers various aspects of the transformation pipeline, including loading interim
> parquet files, parsing production dates, normalizing column names, exploding API numbers, validating
> physical bounds, deduplicating records, sorting and repartitioning data, and writing processed
> parquet files. However, it lacks comprehensive tests for physical bounds validation, water cut
> bounds, and the zero-vs-null distinction after transformation. Additionally, the test for cumulative
> production monotonicity is not explicitly covered.

**test_quality** — PASS (0.80)

> The test suite covers a wide range of scenarios, including happy paths and edge cases, and uses
> various testing techniques such as mocking and parameterization. However, some tests only check the
> return type or mock the entire function under test, which may not thoroughly test the code's
> functionality. Additionally, there are no tests for invalid inputs or extreme values in some test
> functions, which could lead to incomplete testing.

**pipeline_integrity_transform** — PASS (0.80)

> The tests verify the correctness of individual functions, such as load_interim_parquet,
> parse_production_date, and validate_physical_bounds, and also test the overall pipeline. However,
> the tests do not explicitly verify that output Parquet files are partitioned by well_id, and the
> well_id column is present. Additionally, while the tests validate the output schema, they do not
> comprehensively check the dtypes of all columns.

### test_features.py

**domain_correctness_features** — PASS (0.80)

> The test file covers various edge cases for GOR, decline rate, and feature calculations, including
> clipping bounds, shut-in wells, and NaN values. It also verifies the presence of expected feature
> columns and checks for correct calculations of rolling and lag features. However, it does not
> explicitly test the GOR formula for unit-swapped variants or the water cut formula, and some tests
> only cover happy-path values.

**test_quality** — PASS (0.80)

> The test suite covers a wide range of scenarios, including happy paths and edge cases, and uses
> various testing techniques such as mocking and parameterization. However, some tests only check the
> return type or the presence of certain columns, without verifying the actual values or behavior.
> Additionally, there are no tests for invalid or missing inputs, which could lead to incomplete or
> incorrect results.

**pipeline_integrity_features** — PASS (0.80)

> The tests verify the correctness of various feature computation functions, including cumulative
> production, decline rate, rolling features, lag features, time features, and ratio features. They
> also check that the functions return Dask DataFrames and that the output schema is correct. However,
> the tests do not verify that the output Parquet is partitioned by well_id and that each partition
> contains data for exactly one well, and they do not thoroughly validate the full output schema
> including all feature columns with correct dtypes.
