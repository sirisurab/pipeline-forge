# eval/kgs_metrics.py
# Stage-aware GEval metrics for KGS pipeline test quality.
#
# Each pipeline stage has different responsibilities — applying GOR/water cut
# criteria to test_acquire.py is a rubric error, not a test gap. This module
# defines per-stage metric sets and a routing dict used by run_eval.py.
#
# Dimension 1 — domain_correctness : stage-specific physical/domain constraints
# Dimension 2 — test_quality       : same for all stages
# Dimension 3 — pipeline_integrity : stage-specific structural contracts

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from groq_judge import GroqJudge

judge = GroqJudge()

# ---------------------------------------------------------------------------
# Dimension 2 — Test quality (stage-independent)
# ---------------------------------------------------------------------------
test_quality = GEval(
    name="test_quality",
    model=judge,
    evaluation_steps=[
        "Identify any assertions in the test file that are trivially true regardless of "
        "implementation: examples include 'assert result is not None', 'assert len(df) > 0', "
        "'assert isinstance(x, float)'. Count how many of the total assertions fall into this "
        "category. Score lower the higher the ratio of trivial assertions to total assertions.",

        "Identify any tests that would pass even if the function being tested returned a constant "
        "or did nothing. For example: a test that only checks the return type, or one that mocks "
        "the entire function under test and then asserts on the mock's return value. These are "
        "vacuous — they test the test harness, not the code. Penalise each vacuous test found.",

        "Check whether each test function tests only the happy path (valid, typical inputs). "
        "A test file with no tests for invalid inputs, missing data, empty DataFrames, or extreme "
        "values is incomplete regardless of how many test functions it contains. "
        "Penalise test files where >80% of tests use only clean, well-formed inputs.",

        "Check whether tests that compare floating-point outputs use approximate comparison "
        "(pytest.approx, math.isclose, or numpy.testing.assert_allclose) rather than exact "
        "equality. Exact equality on floats (e.g. 'assert result == 0.333') is fragile. "
        "Penalise each instance of exact float equality on computed values.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

# ===========================================================================
# ACQUIRE stage
# ===========================================================================

domain_correctness_acquire = GEval(
    name="domain_correctness_acquire",
    model=judge,
    evaluation_steps=[
        "Check whether the test file tests that the acquire step is idempotent: running it twice "
        "on the same target directory should not duplicate files, corrupt existing files, or raise "
        "an error because a file already exists. Penalise if there is no idempotency test.",

        "Check whether the test file tests acquired file integrity: every downloaded file should "
        "have size greater than 0 bytes, be readable as UTF-8 text, and contain at least one data "
        "row beyond a header. A file that exists on disk but is empty or unreadable is a silent "
        "failure. Penalise if file integrity is not verified.",

        "Check whether the test file tests that the number of downloaded files matches the number "
        "of leases or targets requested. A mismatch indicates a silent partial failure. "
        "Penalise if file count reconciliation is absent.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

pipeline_integrity_acquire = GEval(
    name="pipeline_integrity_acquire",
    model=judge,
    evaluation_steps=[
        "Check whether unit tests use mocking to avoid real network calls to the KGS portal. "
        "A unit test that makes real HTTP requests will fail in CI without network access and "
        "is not a true unit test. Penalise tests marked @pytest.mark.unit that have real network "
        "dependencies rather than mocked ones.",

        "Check whether tests verify the output directory structure after acquire: the expected "
        "subdirectory exists, files are written to the correct location, and filenames follow "
        "the expected naming convention. Penalise if tests only check that a function returns "
        "without error, not that the filesystem state is correct.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

# ===========================================================================
# INGEST stage
# ===========================================================================

domain_correctness_ingest = GEval(
    name="domain_correctness_ingest",
    model=judge,
    evaluation_steps=[
        "Check whether the test file tests the distinction between zero production and missing "
        "data. A well reporting zero production in a month is different from a well with no "
        "record for that month. Zeros must remain as zeros (not be converted to NaN) in the "
        "ingested output. Penalise if this distinction is not explicitly tested.",

        "Check whether the test file tests unit consistency: oil volumes in BBL, gas in MCF, "
        "water in BBL. If the raw KGS data can contain unit variations across wells or time "
        "periods, the ingest stage should normalise them. Test that normalised values fall "
        "within realistic ranges — oil rates above 50,000 BBL/month for a single Kansas "
        "conventional well are almost certainly a unit error. Penalise if unit validation "
        "is absent.",

        "Check whether the test file tests that date parsing produces correct datetime values "
        "from the raw M-YYYY format in KGS data. Penalise if date parsing is not tested or "
        "if only a trivial 'column exists' check is present without verifying parsed values.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

pipeline_integrity_ingest = GEval(
    name="pipeline_integrity_ingest",
    model=judge,
    evaluation_steps=[
        "Check whether tests verify that the ingest output schema is correct: expected column "
        "names present, correct dtypes (datetime64 for date, float64 for production volumes, "
        "string for well_id). Penalise if tests only check row counts or file existence.",

        "Check whether tests verify that the ingest step does not call .compute() internally "
        "— the return type should be dask.dataframe.DataFrame, not pandas.DataFrame. A function "
        "returning pandas has either called .compute() or bypassed Dask entirely. "
        "Penalise if Dask laziness is not tested.",

        "Check whether tests verify row count reconciliation: after deduplication, the processed "
        "row count should be less than or equal to the raw row count. Also test that deduplication "
        "is idempotent — running the cleaning step twice produces the same output as once. "
        "Penalise if neither check is present.",

        "Check whether unit tests use synthetic fixture data rather than reading from data/raw/. "
        "A unit test with a real filesystem dependency will fail in CI without data files. "
        "Penalise tests marked @pytest.mark.unit that read from disk.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

# ===========================================================================
# TRANSFORM stage
# ===========================================================================

domain_correctness_transform = GEval(
    name="domain_correctness_transform",
    model=judge,
    evaluation_steps=[
        "Check whether the test file tests physical bounds validation: production volumes "
        "(oil_bbl, gas_mcf, water_bbl) cannot be negative — any negative value is a sensor "
        "error or pipeline bug and must be caught. Penalise if negative volume handling "
        "is not tested.",

        "Check whether the test file tests water cut bounds. Water cut = water_bbl / "
        "(oil_bbl + water_bbl). Both boundary values are physically valid and must be "
        "accepted: (a) water_cut=0.0 — a new or dry-reservoir well with no water production; "
        "(b) water_cut=1.0 — a late-life well producing 100% water, which is a normal "
        "end-of-life state, NOT a data error. Penalise if the test treats water_cut=1.0 "
        "as invalid or if only interior values like 0.5 are tested.",

        "Check whether the test file tests the zero-vs-null distinction after transform: "
        "zero production values from the raw data must remain as zeros, not be converted "
        "to NaN during cleaning. A well shut in for a month legitimately reports zero. "
        "Penalise if this distinction is not preserved and tested.",

        "Check whether the test file tests that cumulative production (Np, Gp, Wp) is "
        "monotonically non-decreasing per well. Verify three distinct cases are tested: "
        "(a) the decreasing case is rejected; (b) flat periods (shut-in months with zero "
        "production) keep cumulative flat; (c) resumption after shut-in resumes correctly "
        "from the flat value. Penalise if only the basic monotonicity check is present "
        "without the flat-period and resumption cases.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

pipeline_integrity_transform = GEval(
    name="pipeline_integrity_transform",
    model=judge,
    evaluation_steps=[
        "Check whether tests verify that output Parquet files are partitioned by well_id: "
        "each partition contains data for exactly one well, and the well_id column is present. "
        "Penalise if tests only check file existence without verifying partition structure.",

        "Check whether tests validate the output schema: correct column names and dtypes "
        "(float64 for volumes, datetime64 for dates, string/category for well_id). "
        "Penalise if schema is not validated.",

        "Check whether tests verify Dask laziness: pipeline functions should return "
        "dask.dataframe.DataFrame, not pandas.DataFrame. Penalise if not tested.",

        "Check whether unit tests use synthetic fixture DataFrames rather than reading "
        "from disk. Penalise tests marked @pytest.mark.unit that have filesystem dependencies.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

# ===========================================================================
# FEATURES stage
# ===========================================================================

domain_correctness_features = GEval(
    name="domain_correctness_features",
    model=judge,
    evaluation_steps=[
        "Check whether the test file tests GOR (Gas-Oil Ratio = gas_mcf / oil_bbl) edge cases. "
        "Three cases must be covered: (a) oil_bbl=0, gas_mcf>0 — a physically valid late-life "
        "or pure gas well state, not an error. The pipeline must return NaN or a defined sentinel "
        "without raising an exception. Do NOT penalise if this is treated as a valid state. "
        "(b) both oil_bbl=0 and gas_mcf=0 — shut-in well, result should be 0 or NaN, not an "
        "exception. (c) oil_bbl>0, gas_mcf=0 — GOR should be 0.0. Note: very high GOR on low "
        "oil production is physically normal in late-stage reservoir depletion — do not penalise "
        "tests that accept high GOR as valid. Penalise only if tests cover only happy-path values.",

        "Check whether the test file tests decline rate clip bounds. The pipeline clips "
        "period-over-period decline rate to [-1.0, 10.0] as an engineering design decision for "
        "ML feature stability. Tests must verify: (a) values below -1.0 clip to -1.0; "
        "(b) values above 10.0 clip to 10.0; (c) values within bounds pass through unchanged; "
        "(d) a shut-in well (zero production in consecutive months) does not produce an unclipped "
        "extreme before the clip is applied. Penalise if only midrange values are tested.",

        "Check whether the test file tests feature calculation correctness against known synthetic "
        "inputs: (a) rolling 3-month and 6-month averages match hand-computed values; (b) when "
        "window is larger than available history (first 1-2 months), result is NaN or partial, "
        "not silently zero or wrong; (c) lag-1 feature for month N equals month N-1 value; "
        "(d) GOR formula uses gas_mcf / oil_bbl, not a unit-swapped variant; "
        "(e) water cut formula uses water_bbl / (oil_bbl + water_bbl). "
        "Penalise if features are only tested for existence, not for correctness.",

        "Check whether the test file verifies that all expected feature columns are present in "
        "the output: well_id, production_date, oil_bbl, gas_mcf, water_bbl, cum_oil, cum_gas, "
        "cum_water, gor, water_cut, decline_rate, and rolling/lag columns. A run that silently "
        "drops a feature column will pass most other tests. Penalise if column presence is "
        "not verified.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

pipeline_integrity_features = GEval(
    name="pipeline_integrity_features",
    model=judge,
    evaluation_steps=[
        "Check whether tests verify that output Parquet is partitioned by well_id and that "
        "each partition contains data for exactly one well. Penalise if only file existence "
        "is checked.",

        "Check whether tests validate the full output schema including all feature columns "
        "with correct dtypes. Penalise if schema validation is absent or incomplete.",

        "Check whether tests verify Dask laziness: feature engineering functions should return "
        "dask.dataframe.DataFrame. Penalise if .compute() is called inside the pipeline "
        "function rather than by the caller.",

        "Check whether unit tests use synthetic single-well DataFrames as fixtures rather than "
        "reading from processed Parquet files on disk. Penalise tests marked @pytest.mark.unit "
        "that depend on upstream pipeline output.",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.5,
)

# ===========================================================================
# Routing — maps each test file to its applicable metrics
# Used by run_eval.py
# ===========================================================================
STAGE_METRICS = {
    "test_acquire.py": [
        domain_correctness_acquire,
        test_quality,
        pipeline_integrity_acquire,
    ],
    "test_ingest.py": [
        domain_correctness_ingest,
        test_quality,
        pipeline_integrity_ingest,
    ],
    "test_transform.py": [
        domain_correctness_transform,
        test_quality,
        pipeline_integrity_transform,
    ],
    "test_features.py": [
        domain_correctness_features,
        test_quality,
        pipeline_integrity_features,
    ],
}
