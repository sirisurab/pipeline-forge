# Model Behavior Constraints — Anticipation Guide

Read this before delegating to task-writer for any new pipeline spec. Scan the
spec against each pattern below. Where a trigger condition matches, apply the
preventive measure before task-writer runs.

This is an anticipation layer — it tells the orchestrator and task-writer what
failure modes to expect given a spec's structure, so preventive constraints can
be added before a run rather than discovered at runtime.

---

## Pattern 1 — Discovery Injection

**Trigger:** spec provides explicit URLs, file naming templates, or path patterns.

**Behavior:** task-writer reasons "these might change" and adds a discovery step
(index page fetch, directory listing, link scraping) to find the URLs dynamically.

**Preventive:** add to task-writer-{project}.md: "URL construction uses {template}
directly — do not fetch or scrape an index page to discover URLs."

---

## Pattern 2 — Dependency Activation

**Trigger:** build-env-manifest lists a library with broad capability (e.g. BeautifulSoup,
SQLAlchemy, boto3) near a task that touches the same domain.

**Behavior:** task-writer or coder invents a use for the library beyond what the spec
requires, to justify its presence.

**Preventive:** add to the relevant task spec: "library X is present for task Y only —
do not use it in other tasks."

---

## Pattern 3 — Scope-to-full-pattern

**Trigger:** task spec describes a recognizable partial pattern (ETL pipeline, REST
client, file downloader).

**Behavior:** coder implements the full recognized pattern rather than the minimal
slice — adds retry logic, caching, discovery, or validation the spec didn't ask for.

**Preventive:** task spec must state explicitly what is NOT required (no retry logic,
no caching, no discovery, etc.).

---

## Pattern 4 — Prior-driven concretization

**Trigger:** spec or config provides an abstract constraint (minimum version, API
family name, stability requirement).

**Behavior:** coder resolves the abstract constraint to a specific value via training
prior, which may be wrong (e.g. derives `python3.11` from `requires-python = ">=3.11"`).

**Preventive:** in build-env-manifest, give an elimination rule — describe what the
wrong answer looks like — not a principle. Principles are resolved via training prior;
elimination rules are not.

---

## Pattern 5 — Meta helper construction

**Trigger:** task spec is silent on meta derivation for any dd.from_delayed call.

**Behavior:** coder constructs a named helper function or empty-frame builder rather
than calling the actual function on minimal input and slicing to zero rows.

**Preventive:** task spec must cite ADR-003 by name at any function that feeds
dd.from_delayed. Silence on meta is not neutrality — it creates a vacuum the coder
fills with a training prior (helper function).

---

## Pattern 6 — Type uniformity

**Trigger:** task involves multiple column types (nullable ints, floats, strings,
categoricals).

**Behavior:** coder applies one null sentinel uniformly (pd.NA) across all dtypes,
ignoring that pd.NA is invalid for float64 columns.

**Preventive:** task spec must cite ADR-003. Orchestrator should route the first
meta mismatch failure to coder-advanced immediately — do not spend loops on it.

---

## Pattern 7 — Cross-stage data-flow blindness

**Trigger:** fine-grained task decomposition creates more than one function for a
stage transition (read → filter → orchestrate rather than read → orchestrate).

**Behavior:** early returns in orchestrator functions bypass schema enforcement;
upstream data state claims are reasoned rather than derived from boundary contracts.

**Preventive:** task-writer must trace all return paths against the output contract
before finalizing any decomposed task. All return paths of a function must satisfy
the same output contract.

---

## Pattern 8 — Silence as vacuum (task-writer)

**Trigger:** any design decision the coder will face is not covered by a citation
in the task spec.

**Behavior:** coder fills the vacuum with training prior, bypassing the ADR. The
task spec made no mechanism claim, so the Step 4 re-consult trigger never fires.

**Preventive:** before finalizing each task spec, enumerate every implementation
decision the coder will face and verify a governing document citation exists for
each. A task spec that is silent on a governed mechanism is incomplete.

---

## Pattern 9 — Authority inversion (coder)

**Trigger:** task spec makes a mechanism claim that touches an ADR-governed area
(meta derivation, scheduler choice, parallelization approach, Makefile structure).

**Behavior:** coder follows the task spec (more specific) over the ADR (more
general). The ADR loses silently.

**Preventive:** orchestrator must verify task specs don't prescribe mechanisms in
ADR-governed areas before delegating to coder-advanced. If a task spec prescribes
a mechanism, it must cite the governing ADR — not restate or elaborate it.