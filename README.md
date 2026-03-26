# pipeline-forge - an Agentic Coding System for an Oil & Gas Data Pipeline
Agentic AI application that builds a data-pipeline to acquire, ingest and process oil &amp; gas field data

Test case: Kansas Geological Survey well production data, 2020–2025.

---

## What Was Built

The pipeline covers four stages: data acquisition (Playwright), ingestion (Dask), transformation and cleaning with domain-specific validation, and feature engineering (decline curves, rolling stats, GOR). Output is Parquet partitioned by well ID, ready for ML workflows.

Architecture: an orchestrator delegating to three specialized subagents — task-writer (designs component specifications), coder-advanced (implements from specs), coder-basic (applies targeted fixes) — with a deterministic evaluator (ruff, mypy, pytest) closing the feedback loop.

Result on a clean run: 141/141 unit tests passing. Cost: ~$3, 1.5M tokens.

---

## Two Architectures

The system above wasn't the starting point. The first version was a lower-level LangGraph graph with custom context trimming and custom routing. Things broke repeatedly, and fixing each problem built an intuition for how LLMs actually work that is hard to get any other way.

![v1 architecture](architecture_v1.png)

Two lessons stood out. First, LLMs don't think top-down the way humans do. They don't need to progress from requirements → architecture → design → code. Working from priors and current context, they can go directly from requirements → tasks → code — often in parallel. Intermediate design artifacts that would be essential for a human team are often just expensive tokens for an LLM. Second, context bloat is a constant problem. Read and write tool calls append file content to the message history, and stale tool call inputs and outputs accumulate silently. Learning what to keep and what to trim — and when — is one of the core LLM engineering skills.

Switching to deepagents with an orchestrator→subagents architecture addressed context bloat more cleanly than the custom trimming approach: automatic context offloading, filesystem abstraction, subagent context isolation. The codebase also shrank significantly without custom routing and middleware. The tradeoff was less control and more abstraction — which made LangSmith trace analysis essential for understanding what was actually happening inside runs.

![v2 architecture](architecture_v2.png)

---

## Open Problems

**Test quality is a work in progress.** 141 tests pass ruff, mypy, and pytest. LLM-as-judge evaluation is underway to assess whether tests cover real edge cases, boundary values, and domain-correct assertions — things the deterministic evaluator can't catch.

**Run-to-run reliability is uncharacterised.** One clean documented run at $3/1.5M tokens. Not enough runs of the same configuration to know how stable that is. More testing underway.

**Data security and governance are not addressed.** Public KGS data only. No authentication, no data governance, no client constraints.

---

## Next

LLM-as-judge evaluation (DeepEval, Groq) for test coverage, code readability, and edge case handling — specifically domain-aware tests.

---

## Stack

LangGraph · deepagents · Claude Sonnet 4.6 · Claude Haiku 4.5 · Dask · Pandas · Playwright · ruff · mypy · pytest · LangSmith · KGS Kansas 2020–2025 · Parquet
