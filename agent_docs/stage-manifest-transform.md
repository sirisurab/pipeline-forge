# Stage Manifest: transform

Describes the purpose, input state, output state, and shared state hazards for
the transform stage. Read this file before implementing any transform tasks.

The manifest describes WHAT the stage must guarantee — not HOW to implement it.
Implementation decisions belong in task specs.

---

## Purpose
Clean, filter, cast categoricals, index by entity column, and sort by production
date. Produce analysis-ready Parquet for feature engineering.

## Input state
- Canonical schema, data-dictionary dtypes
- Unsorted
- max(10, min(n, 50)) partitions

## Output state
- Entity-indexed on {entity_col}
- Sorted by production_date within each partition
- Categoricals cast to declared category sets
- Invalid values replaced with the appropriate null sentinel
- max(10, min(n, 50)) partitions

## Shared state hazards

**H1:** Temporal sort correctness depends on when sorting occurs relative to entity
indexing — the distributed shuffle triggered by the entity indexing operation
destroys any prior row ordering. Sort by production_date must be valid at
stage exit regardless of how it is achieved.

**H2:** Categorical columns must carry only declared category values at stage exit —
values outside the declared set indicate dirty data that must be resolved before
casting, not after.

**H3:** Partition count at stage exit must equal the value mentioned in output state —
no operation after repartition may alter partition structure.

**H4:** `set_index` must be the last structural operation before writing — all
operations that reference the entity column must complete before `set_index` is called.
