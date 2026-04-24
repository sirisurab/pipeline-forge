# Build Environment Manifest

Describes the requirements for all build and environment artifacts — package
configuration, Makefile targets, config structure, and pipeline orchestration.
Read this file before implementing any build, environment, or configuration tasks.

The manifest describes WHAT the build environment must guarantee — not HOW to
implement it. Implementation decisions belong in task specs.

---

## Purpose
Establish a reproducible, installable project environment with a consistent
pipeline entry point, structured configuration, and correct dependency management.

## Build backend

The package build backend must be explicitly declared — never rely on setuptools
defaults. The backend must be the primary public entry point exposed by the
package installer — not an internal alias, submodule, or path containing words
like `backends` or `legacy`. Internal submodule paths are not part of the public
API and are not guaranteed to be present across installer versions. If uncertain,
verify: the module path must be directly importable after a clean `pip install`
of the installer package.

## Environment setup

The project must provide a target to create a clean virtual environment and a
target to install all dependencies including development tools. The install
sequence must bootstrap the package installer itself before installing project
dependencies — never assume the installer is up to date.

The Makefile venv target must invoke the unversioned Python interpreter
(e.g. `python3`). Never derive a specific binary name (e.g. `python3.11`) from
`requires-python` in pyproject.toml — that field declares the minimum version
floor, not the binary name available on the target machine.

## Pipeline targets

The Makefile must expose individual stage targets and a full pipeline target:
- Individual stages must be runnable independently
- The full pipeline target must run all stages in order:
  acquire → ingest → transform → features
- The full pipeline target must use exactly one invocation approach —
  either invoke the pipeline entry point once for all stages, or chain
  stage targets as dependencies with no recipe body. Never combine both:
  a pipeline target that both chains stage targets as dependencies AND
  invokes the entry point in the recipe body will run every stage twice.

## Pipeline entry point

The pipeline package must expose a command-line entry point registered in the
package configuration. The entry point must accept an optional list of stages
to run — defaulting to all four when not specified.

The entry point must:
- Read all settings from config.yaml
- Set up logging before any stage runs
- Run each stage in order with per-stage timing and error logging
- Stop execution on stage failure — downstream stages must not run if an
  upstream stage fails

## Configuration structure

All configurable values must be read from config.yaml. No configurable values
may be hardcoded in pipeline code or read directly from environment variables.

config.yaml must have the following top-level sections:

```
acquire:    all acquire stage settings (URLs, years, workers, output paths)
ingest:     all ingest stage settings
transform:  all transform stage settings
features:   all features stage settings
dask:
  scheduler:         "local" for local distributed cluster, or "tcp://host:port" for remote
  n_workers:         number of worker processes
  threads_per_worker: threads per worker
  memory_limit:      memory cap per worker (e.g. "3GB")
  dashboard_port:    port for the Dask dashboard
logging:
  log_file:  path to log file (e.g. "logs/pipeline.log")
  level:     log level (e.g. "INFO")
```

## Dask scheduler initialization

The pipeline entry point initializes the distributed scheduler after acquire
completes and before ingest begins. Scheduler type is determined by config.yaml:
- If dask.scheduler is "local" → initialize a local distributed cluster with
  settings from the dask section of config.yaml
- If dask.scheduler is a URL → connect to the remote scheduler at that address

The dashboard URL must be logged after initialization.

Individual stages (ingest, transform, features) must reuse an existing scheduler
client if one is already running — they must not initialize their own cluster
when invoked through the pipeline entry point.

## HTTP library for acquire

The acquire stage must use the standard HTTP request library and HTML parsing
library for all download and page-parsing tasks. Browser automation tools are
prohibited — they introduce unnecessary complexity and fragility for data
acquisition tasks.

## Dependencies

Runtime dependencies must include the Dask dashboard library — it is required
at runtime, not only during development.

Development dependencies must include type stub packages for pandas and the HTTP
request library — without these, static type checking fails on every run.

## Version control exclusions

The following must be added to .gitignore:
- data/           (raw, interim, processed data files)
- logs/           (runtime log files)
- large_tool_results/
- conversation_history/
