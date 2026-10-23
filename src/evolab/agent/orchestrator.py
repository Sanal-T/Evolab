"""A bounded loop that validates and executes planner actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from evolab.agent.actions import Action
from evolab.tasks import Task
from evolab.tools.registry import TestResult, ToolError, ToolRegistry


class Planner(Protocol):
    """Interface for a future LLM-backed action planner."""

    def next_action(self, state: "AgentState") -> Action: ...


@dataclass
class AgentEvent:
    action: str
    observation: str


@dataclass
class AgentState:
    task: Task
    max_actions: int
    events: list[AgentEvent] = field(default_factory=list)
    tests_passed: bool = False
    success: bool = False
    termination_reason: str = "action_limit_reached"
    finished: bool = False


@dataclass(frozen=True)
class RunSummary:
    task_id: str
    success: bool
    actions_used: int
    termination_reason: str
    events: tuple[AgentEvent, ...]


class Agent:
    """Execute planner-selected, allow-listed tools up to a fixed limit."""

    _ALLOWED_ACTIONS = {
        "list_files",
        "read_file",
        "search",
        "replace_in_file",
        "run_tests",
        "inspect_diff",
        "finish",
    }

    def __init__(self, planner: Planner, tools: ToolRegistry, max_actions: int = 8) -> None:
        if max_actions < 1:
            raise ValueError("max_actions must be at least 1")
        self.planner = planner
        self.tools = tools
        self.max_actions = max_actions

    def run(self, task: Task) -> RunSummary:
        state = AgentState(task=task, max_actions=self.max_actions)
        while len(state.events) < state.max_actions and not state.finished:
            action = self.planner.next_action(state)
            if not isinstance(action, Action) or action.kind not in self._ALLOWED_ACTIONS:
                state.events.append(AgentEvent("invalid_action", "Planner requested an unknown action."))
                state.termination_reason = "invalid_action"
                break
            try:
                observation = self._execute(action, state)
            except (ToolError, KeyError, TypeError, ValueError) as exc:
                observation = f"Action failed: {exc}"
                if action.kind == "finish":
                    state.termination_reason = "invalid_finish"
                    state.finished = True
            state.events.append(AgentEvent(action.kind, observation))

        return RunSummary(
            task_id=task.task_id,
            success=state.success,
            actions_used=len(state.events),
            termination_reason=state.termination_reason,
            events=tuple(state.events),
        )

    def _execute(self, action: Action, state: AgentState) -> str:
        args = action.arguments
        if action.kind == "list_files":
            return "\n".join(self.tools.list_files())
        if action.kind == "read_file":
            return self.tools.read_file(args["path"])
        if action.kind == "search":
            return repr(self.tools.search(args["text"]))
        if action.kind == "replace_in_file":
            observation = self.tools.replace_in_file(
                args["path"], args["old_text"], args["new_text"]
            )
            state.tests_passed = False
            return observation
        if action.kind == "run_tests":
            result: TestResult = self.tools.run_tests()
            state.tests_passed = result.passed
            state.termination_reason = "tests_passed" if result.passed else "tests_failed"
            return result.output or ("Tests passed." if result.passed else "Tests failed without output.")
        if action.kind == "inspect_diff":
            return self.tools.inspect_diff()
        if action.kind == "finish":
            state.success = state.tests_passed
            state.finished = True
            state.termination_reason = "verified_success" if state.success else "finished_without_passing_tests"
            return "Task complete." if state.success else "Cannot report success: task tests have not passed."
        raise ToolError(f"Unsupported action: {action.kind}")


class ExamplePlanner:
    """Offline demonstration planner for the first curated task.

    This fixed sequence demonstrates the agent/tool workflow; it is not an
    LLM and does not learn how to solve other tasks.
    """

    _SEQUENCE = (
        Action("list_files"),
        Action("read_file", {"path": "solution.py"}),
        Action(
            "replace_in_file",
            {
                "path": "solution.py",
                "old_text": "    return sorted(values)[-2]",
                "new_text": (
                    "    distinct_values = sorted(set(values))\n"
                    "    if len(distinct_values) < 2:\n"
                    "        raise ValueError(\"At least two distinct values are required\")\n"
                    "    return distinct_values[-2]"
                ),
            },
        ),
        Action("run_tests"),
        Action("inspect_diff"),
        Action("finish"),
    )

    def next_action(self, state: AgentState) -> Action:
        if state.task.task_id != "second-largest-distinct":
            return Action("finish")
        index = len(state.events)
        return self._SEQUENCE[index] if index < len(self._SEQUENCE) else Action("finish")
