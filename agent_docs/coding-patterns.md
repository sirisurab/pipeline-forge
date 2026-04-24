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