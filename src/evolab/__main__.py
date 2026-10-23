"""Small command-line entry point for inspecting the task catalog."""

import argparse
from pathlib import Path

from evolab.tasks import load_tasks
from evolab.tools.registry import ToolError, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "datasets" / "task_manifest.json"


def find_task(manifest: Path, task_id: str):
    for task in load_tasks(manifest):
        if task.task_id == task_id:
            return task
    raise SystemExit(f"Unknown task: {task_id}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="evolab")
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list-tasks", help="List approved tasks")
    list_command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    inspect_command = commands.add_parser("inspect-task", help="Inspect task source files")
    inspect_command.add_argument("task_id")
    inspect_command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    test_command = commands.add_parser("run-tests", help="Run a task's approved tests")
    test_command.add_argument("task_id")
    test_command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    if args.command == "list-tasks":
        for task in load_tasks(args.manifest):
            print(f"{task.task_id}: {task.title} ({task.split})")
            print(f"  {task.description}")
    elif args.command == "inspect-task":
        task = find_task(args.manifest, args.task_id)
        tools = ToolRegistry(PROJECT_ROOT, task)
        print(f"Task: {task.title}")
        for relative_path in tools.list_files():
            print(f"\n--- {relative_path} ---")
            print(tools.read_file(relative_path))
    elif args.command == "run-tests":
        task = find_task(args.manifest, args.task_id)
        result = ToolRegistry(PROJECT_ROOT, task).run_tests()
        print("PASSED" if result.passed else "FAILED")
        print(result.output)
        if result.timed_out:
            print("Test run exceeded the time limit.")
        if not result.passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
