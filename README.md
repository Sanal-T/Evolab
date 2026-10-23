# EvoLab

EvoLab is an experimental Python debugging agent. The project will be built in small stages, beginning with a reliable baseline before adding skill retrieval or skill evolution.

## Current stage

The repository contains the initial Python package setup, a task manifest, a small debugging fixture, and a task loader. The agent and LLM connection have not been added yet.

## Set up the development environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## See the available tasks

```powershell
python -m evolab list-tasks
```

The first fixture asks for the second-largest distinct integer. Its current implementation has a bug; its tests describe the expected behavior.

## Inspect a task

```powershell
python -m evolab inspect-task second-largest-distinct
```

This shows the fixture's source files. The inspection tool hides its `tests` directory and prevents paths from escaping the fixture.

## Run a task's tests

```powershell
python -m evolab run-tests second-largest-distinct
```

The first run is expected to fail because the starter implementation is intentionally incorrect. The runner uses a fixed pytest invocation and a 30-second timeout. It is not an operating-system sandbox, so only run reviewed task fixtures.

## Current limitations

There is not yet an LLM client or an agent loop. At this stage, the project can load tasks, inspect approved source files, and run a task's tests.
