# Boundary Contract: ingest → transform

Describes what ingest guarantees to deliver and what transform can rely on
receiving. Read this file when implementing any task that reads ingest output
or writes transform input.

---

## Upstream guarantee (what ingest promises to deliver)
- Column names conform to canonical schema
- All columns carry data-dictionary dtypes
- Nullable absent columns filled with NA
- Partitions: max(10, min(n, 50))
- Sort: unsorted

## Downstream reliance (what transform can rely on)
- Canonical schema is established — no column name
  reconciliation or re-derivation is needed
- Data-dictionary dtypes are enforced — no re-casting
  of columns on read
- All nullable columns are present — no absent nullable
  column handling is needed
- Partition count is within contract range — no
  re-partitioning is needed before processing begins
