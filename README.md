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
