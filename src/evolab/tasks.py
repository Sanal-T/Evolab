"""Load approved task descriptions from the project manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    """A small, reproducible debugging problem."""

    task_id: str
    title: str
    description: str
    category: str
    language: str
    fixture_reference: str
    test_command: str
    expected_behavior: str
    split: str


def load_tasks(manifest_path: Path) -> list[Task]:
    """Read task metadata from a JSON manifest."""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read task manifest: {manifest_path}") from exc

    if not isinstance(data, list):
        raise ValueError("Task manifest must contain a JSON list")

    tasks: list[Task] = []
    seen_ids: set[str] = set()
    required_fields = {field for field in Task.__dataclass_fields__}

    for index, item in enumerate(data):
        if not isinstance(item, dict) or not required_fields.issubset(item):
            raise ValueError(f"Task entry {index} is missing required fields")
        task = Task(**{field: item[field] for field in required_fields})
        if task.task_id in seen_ids:
            raise ValueError(f"Duplicate task_id: {task.task_id}")
        seen_ids.add(task.task_id)
        tasks.append(task)

    return tasks
