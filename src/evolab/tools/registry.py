"""Filesystem and test tools scoped to an approved task fixture."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
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
        self.fixture_root = (self.project_root / task.fixture_reference).resolve()
        if not self._is_within(self.fixture_root, tasks_root):
            raise ToolError("Task fixture must be inside the project's tasks directory")
        if not self.fixture_root.is_dir():
            raise ToolError(f"Task fixture does not exist: {task.fixture_reference}")
        self.task = task

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

    def run_tests(self) -> TestResult:
        """Run only this fixture's tests with a fixed executable and timeout.

        This uses a subprocess and fixed pytest arguments, but is not an OS-level
        sandbox. Only run fixtures that have been reviewed and approved.
        """
        relative_fixture = self.fixture_root.relative_to(self.project_root)
        test_directory = relative_fixture / "tests"
        if not (self.project_root / test_directory).is_dir():
            raise ToolError("This task has no tests directory")

        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        source_path = str(self.project_root / "src")
        environment["PYTHONPATH"] = source_path
        command = [sys.executable, "-m", "pytest", str(test_directory)]
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
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
