from pathlib import Path

import pytest

from evolab.agent.actions import Action
from evolab.agent.orchestrator import Agent, ExamplePlanner
from evolab.tasks import load_tasks
from evolab.tools.registry import ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_example_task():
    return load_tasks(PROJECT_ROOT / "datasets" / "task_manifest.json")[0]


def test_example_agent_solves_task_without_changing_reference_fixture():
    task = get_example_task()
    source_path = PROJECT_ROOT / task.fixture_reference / "solution.py"
    original_source = source_path.read_text(encoding="utf-8")

    summary = Agent(
        ExamplePlanner(), ToolRegistry(PROJECT_ROOT, task), max_actions=8
    ).run(task)

    assert summary.success is True
    assert summary.termination_reason == "verified_success"
    assert summary.actions_used <= 8
    assert source_path.read_text(encoding="utf-8") == original_source


class FinishImmediately:
    def next_action(self, state):
        return Action("finish")


def test_agent_cannot_claim_success_without_passing_tests():
    task = get_example_task()
    summary = Agent(
        FinishImmediately(), ToolRegistry(PROJECT_ROOT, task), max_actions=2
    ).run(task)

    assert summary.success is False
    assert summary.termination_reason == "finished_without_passing_tests"


class EditAfterTesting:
    def __init__(self):
        self.actions = [
            Action(
                "replace_in_file",
                {
                    "path": "solution.py",
                    "old_text": "    return sorted(values)[-2]",
                    "new_text": (
                        "    distinct_values = sorted(set(values))\n"
                        "    if len(distinct_values) < 2:\n"
                        "        raise ValueError(\"need two values\")\n"
                        "    return distinct_values[-2]"
                    ),
                },
            ),
            Action("run_tests"),
            Action(
                "replace_in_file",
                {
                    "path": "solution.py",
                    "old_text": "return distinct_values[-2]",
                    "new_text": "return distinct_values[-1]",
                },
            ),
            Action("finish"),
        ]

    def next_action(self, state):
        return self.actions[len(state.events)]


def test_success_requires_tests_after_the_last_edit():
    task = get_example_task()
    summary = Agent(
        EditAfterTesting(), ToolRegistry(PROJECT_ROOT, task), max_actions=4
    ).run(task)

    assert summary.success is False
    assert summary.termination_reason == "finished_without_passing_tests"


def test_agent_rejects_zero_action_limit():
    task = get_example_task()

    with pytest.raises(ValueError, match="at least 1"):
        Agent(ExamplePlanner(), ToolRegistry(PROJECT_ROOT, task), max_actions=0)
