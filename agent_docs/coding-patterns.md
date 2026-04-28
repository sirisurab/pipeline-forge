# Coding Patterns

Cross-cutting implementation guidance for all pipeline coders.

> **Before adding a pattern here:** it must be (1) necessary — a recurring error class that
> causes real failures, not a style preference — and (2) generic — stated at intent level,
> not tied to a specific library, column name, or pipeline. If a pattern only applies to one
> stage or one project, it belongs in the stage manifest or project task-writer file instead.

---

## mypy Union Type Errors

When mypy reports `[union-attr]`, `[index]`, or `[operator]` on a value of union type, use
`isinstance` narrowing to establish the specific type before the operation. These errors
cannot be suppressed with `# type: ignore` — they indicate a genuine runtime risk that must
be resolved with a code fix.

---

## Test Assertion Semantics for NumPy and pandas Types

When asserting boolean values on numpy scalars or pandas Series:
- Never use `is True` / `is False` — numpy scalar types are not Python bool instances;
  identity checks fail even when equality holds. Use `== True` / `== False` or cast to
  Python bool.
- Never use `== False` on a pandas Series — ruff E712 flags this. Use `~series`
  (bitwise not) for boolean Series negation.

---

## Test Variable Discipline

Assign variables in test bodies only if they are referenced in at least one assertion.
Assignments that are never read produce ruff F841 errors. Use expressions directly in
assertions where the value is not reused.