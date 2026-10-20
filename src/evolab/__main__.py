"""Small command-line entry point for inspecting the task catalog."""

import argparse
from pathlib import Path

from evolab.tasks import load_tasks


def main() -> None:
    parser = argparse.ArgumentParser(prog="evolab")
    parser.add_argument("command", choices=["list-tasks"])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("datasets/task_manifest.json"),
        help="Path to the task manifest",
    )
    args = parser.parse_args()

    if args.command == "list-tasks":
        for task in load_tasks(args.manifest):
            print(f"{task.task_id}: {task.title} ({task.split})")
            print(f"  {task.description}")


if __name__ == "__main__":
    main()
