# Stage Manifest: features

Describes the purpose, input state, output state, and shared state hazards for
the features stage. Read this file before implementing any features tasks.

The manifest describes WHAT the stage must guarantee — not HOW to implement it.
Implementation decisions belong in task specs.

---

## Purpose
Compute all derived features required for ML workflows — cumulative volumes, GOR,
water cut, decline rates, rolling averages, lag features, encoded categoricals.
Produce ML-ready Parquet files in data/processed/.

## Input state
- Entity-indexed on {entity_col}
- Sorted by production_date within each partition
- Categoricals cast
- max(10, min(n, 50)) partitions

## Output state
All input columns plus derived feature columns. ML-ready Parquet files in
data/processed/.

## Shared state hazards

**H1:** All time-dependent features (cumulative sums, rolling windows, lag features,
decline rates) require correct temporal ordering within each entity group — the
sort established in transform must be preserved at the point each feature is
computed.
