# KGS Pipeline — LLM Judge Eval Results
*Generated: 2026-04-01 14:28*
*Judge: Groq / llama-3.3-70b-versatile*

## Summary

| File | domain_correctness_acquire | test_quality | pipeline_integrity_acquire |
|---||---||---||---|
| test_acquire.py | ✓ 0.80 | ✓ 0.70 | ✓ 0.80 |

| File | domain_correctness_ingest | test_quality | pipeline_integrity_ingest |
|---||---||---||---|
| test_ingest.py | ✓ 0.80 | ✓ 0.80 | ✓ 0.80 |

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

> The test file does test the idempotency of the download_file function, ensuring that running it
> twice on the same target directory does not duplicate files or raise an error. It also tests the
> integrity of the acquired files by checking their size and readability. However, it does not
> explicitly test that the number of downloaded files matches the number of leases or targets
> requested, which could indicate a silent partial failure.

**test_quality** — PASS (0.70)

> The test suite covers various scenarios, including happy paths and edge cases, with a good balance
> of tests for different functions. However, some tests only check for the existence of files or the
> type of the result, without verifying the actual content or values. Additionally, there are no tests
> that check for invalid or missing inputs, and some tests use exact equality for floating-point
> comparisons. The test suite also lacks tests for error handling and boundary cases.

**pipeline_integrity_acquire** — PASS (0.80)

> The tests use mocking to avoid real network calls, which is good practice. However, the tests do not
> thoroughly verify the output directory structure after acquire, only checking that a function
> returns without error in some cases.

### test_ingest.py

**domain_correctness_ingest** — PASS (0.80)

> The test file thoroughly checks the ingestion process, including reading raw files, validating
> schema, coercing types, filtering date ranges, and running the ingest process. It also tests for
> zero production retention and schema completeness across partitions. However, it does not explicitly
> test the distinction between zero production and missing data, and unit consistency is only
> partially tested.

**test_quality** — PASS (0.80)

> The test suite covers various aspects of the ingest pipeline, including reading raw files,
> validating schema, coercing types, filtering date ranges, and running the ingest process. It also
> checks for required columns, handles partial failures, and verifies the correctness of the output.
> However, some tests only check the happy path, and there are no explicit tests for extreme values or
> missing data. Additionally, some assertions are trivially true, such as checking the type of the
> result.

**pipeline_integrity_ingest** — PASS (0.80)

> The tests verify the ingest output schema, checking for correct column names and dtypes, and ensure
> that the ingest step does not call .compute() internally, returning a dask.dataframe.DataFrame. The
> tests also verify row count reconciliation and use synthetic fixture data. However, the tests do not
> fully verify deduplication idempotence and do not comprehensively check Dask laziness.

### test_transform.py

**domain_correctness_transform** — PASS (0.60)

> The test file covers various aspects of data transformation and validation, including handling
> nulls, removing duplicates, capping outliers, and deriving production dates. However, it lacks
> comprehensive tests for physical bounds validation, water cut bounds, and the zero-vs-null
> distinction after transformation. Additionally, the tests for cumulative production do not
> explicitly cover the required distinct cases, such as the decreasing case, flat periods, and
> resumption after shut-in.

**test_quality** — PASS (0.80)

> The test suite covers a wide range of scenarios, including happy paths and edge cases, and uses
> approximate comparison for floating-point outputs. However, some tests only check the return type or
> mock the entire function under test, and there are no tests for extreme values or invalid inputs in
> certain functions.

**pipeline_integrity_transform** — PASS (0.80)

> The tests verify the output schema, validate Dask laziness, and use synthetic fixture DataFrames.
> However, they do not explicitly check if output Parquet files are partitioned by well_id, and some
> tests marked @pytest.mark.unit have filesystem dependencies.

### test_features.py

**domain_correctness_features** — PASS (0.80)

> The test file covers various edge cases for GOR, decline rate clip bounds, and feature calculation
> correctness, including tests for NaN and zero values. It also verifies the presence of expected
> feature columns in the output. However, some tests only cover happy-path values, and there is room
> for improvement in testing more extreme or edge cases, such as very high GOR on low oil production.

**test_quality** — PASS (0.80)

> The test suite covers a wide range of scenarios, including edge cases and error handling, and uses
> approximate comparison for floating-point outputs. However, some tests only check the return type or
> mock the entire function under test, and there are no tests for invalid inputs or extreme values in
> certain functions.

**pipeline_integrity_features** — PASS (0.80)

> The tests verify the correctness of various feature engineering functions, including
> compute_cumulative, compute_ratios, compute_decline_rate, compute_rolling, and compute_lags, and
> also check the schema stability across partitions. However, the tests do not explicitly verify that
> the output Parquet is partitioned by well_id and that each partition contains data for exactly one
> well, and some tests depend on upstream pipeline output.
