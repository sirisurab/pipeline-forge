# Boundary Contract: transform → features

Describes what transform guarantees to deliver and what features can rely on
receiving. Read this file when implementing any task that reads transform output
or writes features input.

---

## Upstream guarantee (what transform promises to deliver)
- Entity-indexed on {entity_col}
- Sorted by production_date within each partition
- Categoricals cast to declared category sets
- Invalid values replaced with the appropriate null sentinel
- Partitions: max(10, min(n, 50))

## Downstream reliance (what features can rely on)
- Temporal ordering is correct within each entity group —
  no re-sorting is needed before computing time-dependent
  features
- Entity index is established — no re-indexing is needed
- Categoricals are cast and clean — no re-casting or
  re-validation of categorical columns is needed
- Invalid values are already replaced with the appropriate null sentinel — no
  additional null handling for invalid values is needed
- Partition count is within contract range — no
  re-partitioning is needed before processing begins
