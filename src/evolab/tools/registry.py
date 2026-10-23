"""Filesystem and test tools scoped to an approved task fixture."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from evolab.tasks import Task


class ToolError(ValueError):
    """Raised when a requested operation is outside the tool's permissions."""


@dataclass(frozen=True)
class TestResult:
    """The bounded result of running a task's approved tests."""

    passed: bool
    return_code: int
    output: str
    timed_out: bool = False


class ToolRegistry:
    """Expose a small set of operations limited to one task fixture."""

    _READABLE_SUFFIXES = {".py", ".md", ".json", ".toml"}
    _MAX_FILE_BYTES = 100_000
    _MAX_OUTPUT_CHARS = 20_000
    _TEST_TIMEOUT_SECONDS = 30

    def __init__(self, project_root: Path, task: Task) -> None:
        self.project_root = project_root.resolve()
        tasks_root = (self.project_root / "tasks").resolve()
        approved_fixture = (self.project_root / task.fixture_reference).resolve()
        if not self._is_within(approved_fixture, tasks_root):
            raise ToolError("Task fixture must be inside the project's tasks directory")
        if not approved_fixture.is_dir():
            raise ToolError(f"Task fixture does not exist: {task.fixture_reference}")
        self._temporary_workspace = tempfile.TemporaryDirectory(
            prefix=".evolab-run-", dir=self.project_root
        )
        self.fixture_root = Path(self._temporary_workspace.name) / task.task_id
        shutil.copytree(approved_fixture, self.fixture_root)
        self.task = task
        self._original_sources = {
            relative_path: self.read_file(relative_path)
            for relative_path in self.list_files()
            if Path(relative_path).suffix.lower() == ".py"
        }

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _source_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ToolError("Use a path relative to the task fixture")
        resolved = (self.fixture_root / candidate).resolve()
        if not self._is_within(resolved, self.fixture_root):
            raise ToolError("Requested file is outside the task fixture")
        if "tests" in resolved.relative_to(self.fixture_root).parts:
            raise ToolError("Task tests are not available for source inspection")
        if resolved.suffix.lower() not in self._READABLE_SUFFIXES:
            raise ToolError("This file type is not available for source inspection")
        if not resolved.is_file():
            raise ToolError("Requested source file does not exist")
        if resolved.stat().st_size > self._MAX_FILE_BYTES:
            raise ToolError("Requested source file is too large")
        return resolved

    def list_files(self) -> list[str]:
        """List readable files while hiding tests and hidden directories."""
        files: list[str] = []
        for path in self.fixture_root.rglob("*"):
            relative = path.relative_to(self.fixture_root)
            if not path.is_file() or "tests" in relative.parts:
                continue
            if any(part.startswith(".") for part in relative.parts):
                continue
            if path.suffix.lower() in self._READABLE_SUFFIXES:
                files.append(relative.as_posix())
        return sorted(files)

    def read_file(self, relative_path: str) -> str:
        """Read one approved source file from the fixture."""
        return self._source_path(relative_path).read_text(encoding="utf-8")

    def search(self, text: str) -> dict[str, list[int]]:
        """Find a text fragment in readable files, returning matching line numbers."""
        if not text:
            raise ToolError("Search text must not be empty")
        matches: dict[str, list[int]] = {}
        for relative_path in self.list_files():
            contents = self.read_file(relative_path)
            line_numbers = [
                number
                for number, line in enumerate(contents.splitlines(), start=1)
                if text in line
            ]
            if line_numbers:
                matches[relative_path] = line_numbers
        return matches

    def replace_in_file(self, relative_path: str, old_text: str, new_text: str) -> str:
        """Replace one exact source fragment; refuse ambiguous or empty edits."""
        if not old_text:
            raise ToolError("The text to replace must not be empty")
        path = self._source_path(relative_path)
        original = path.read_text(encoding="utf-8")
        occurrences = original.count(old_text)
        if occurrences != 1:
            raise ToolError(f"Expected one matching fragment, found {occurrences}")
        updated = original.replace(old_text, new_text, 1)
        if len(updated.encode("utf-8")) > self._MAX_FILE_BYTES:
            raise ToolError("Updated source file is too large")
        path.write_text(updated, encoding="utf-8")
        return "Source file updated"

    def inspect_diff(self) -> str:
        """Show changes to Python source files since this tool session began."""
        chunks: list[str] = []
        for relative_path, before in self._original_sources.items():
            after = self.read_file(relative_path)
            if before == after:
                continue
            chunks.extend(
                unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=f"before/{relative_path}",
                    tofile=f"after/{relative_path}",
                )
            )
        return "".join(chunks) or "No source changes."

    def run_tests(self) -> TestResult:
        """Run only this fixture's tests with a fixed executable and timeout.

        This uses a subprocess and fixed pytest arguments, but is not an OS-level
        sandbox. Only run fixtures that have been reviewed and approved.
        """
        test_directory = self.fixture_root / "tests"
        if not test_directory.is_dir():
            raise ToolError("This task has no tests directory")

        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        source_path = str(self.project_root / "src")
        environment["PYTHONPATH"] = os.pathsep.join((source_path, str(self.fixture_root)))
        command = [sys.executable, "-m", "pytest", "tests"]
        try:
            result = subprocess.run(
                command,
                cwd=self.fixture_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=self._TEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return TestResult(
                passed=False,
                return_code=-1,
                output=output[-self._MAX_OUTPUT_CHARS :],
                timed_out=True,
            )

        output = result.stdout + result.stderr
        return TestResult(
            passed=result.returncode == 0,
            return_code=result.returncode,
            output=output[-self._MAX_OUTPUT_CHARS :],
        )
