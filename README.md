# pipeline-forge
Agentic AI application that builds a data-pipeline to acquire, ingest and process oil &amp; gas field data

## Directory Structure
dapi_poc/
├── Agent.py                  ← graph assembly
├── planner.md                ← system prompt for planner
├── coder.md                  ← system prompt for coder
├── pyproject.toml
├── .env
└── agent/
    ├── __init__.py
    ├── state.py              ← graph state
    ├── tools.py              ← tools
    ├── middleware.py         ← middleware for sub-agents
    ├── planner.py            ← planner
    ├── coder.py              ← coder
    ├── evaluator.py          ← evaluator
    ├── human_in_loop.py      ← human-in-loop
    └── edges.py              ← conditional edges
