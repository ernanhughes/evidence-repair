"""Read-only repository tools exposed to repair programs."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from .artifacts import fingerprint


@dataclass(frozen=True)
class ToolResult:
    """Structured result from a repository tool call."""

    ok: bool
    error: str | None
    data: object

    def to_record(self) -> dict[str, object]:
        return asdict(self)


class RepositoryTools:
    """A deliberately small read-only tool surface for a bound repository."""

    def __init__(
        self,
        root: Path,
        *,
        max_results: int = 20,
        max_line_window: int = 80,
    ) -> None:
        self.root = root.resolve()
        self.max_results = max_results
        self.max_line_window = max_line_window

    def _resolve(self, path: str) -> Path:
        candidate = (self.root / path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("path escapes repository root")
        return candidate

    def _iter_safe_files(self, pattern: str = "*") -> Iterator[Path]:
        for path in sorted(self.root.rglob(pattern)):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved == self.root or self.root in resolved.parents:
                yield resolved

    def search_repository(self, query: str) -> ToolResult:
        """Search file paths and UTF-8 file contents for a plain-text query."""

        needle = query.strip().lower()
        if not needle:
            return ToolResult(False, "empty query", [])

        matches: list[dict[str, object]] = []

        for path in self._iter_safe_files("*"):
            relative = path.relative_to(self.root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if needle in relative.lower() or needle in text.lower():
                matches.append({"path": relative})
            if len(matches) >= self.max_results:
                break

        return ToolResult(True, None, matches)

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> ToolResult:
        """Read a bounded line window from a repository-relative file."""

        if start_line < 1:
            return ToolResult(False, "start_line must be >= 1", None)

        try:
            resolved = self._resolve(path)
        except ValueError as exc:
            return ToolResult(False, str(exc), None)

        if not resolved.exists() or not resolved.is_file():
            return ToolResult(False, "missing file", None)

        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return ToolResult(False, "decode_error", None)

        if start_line > len(lines):
            return ToolResult(False, "start_line beyond end of file", None)

        final = len(lines) if end_line is None else end_line
        if final < start_line:
            return ToolResult(False, "end_line must be >= start_line", None)
        if final - start_line + 1 > self.max_line_window:
            return ToolResult(False, "line window too large", None)

        selected = [
            {"line": idx, "text": lines[idx - 1]}
            for idx in range(start_line, min(final, len(lines)) + 1)
        ]

        return ToolResult(
            True,
            None,
            {
                "path": resolved.relative_to(self.root).as_posix(),
                "start_line": start_line,
                "end_line": min(final, len(lines)),
                "lines": selected,
            },
        )

    def inspect_symbol(self, name: str) -> ToolResult:
        """Inspect Python functions and classes with a matching name."""

        hits: list[dict[str, object]] = []

        for path in self._iter_safe_files("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if not isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                ):
                    continue
                if node.name != name:
                    continue

                hits.append(
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "kind": type(node).__name__,
                        "line": node.lineno,
                    }
                )
                if len(hits) >= self.max_results:
                    return ToolResult(True, None, hits)

        return ToolResult(True, None, hits)


class ToolAudit:
    """Record every LM-visible repository tool call.

    DSPy tools can return strings, so the wrapper returns JSON observations
    while preserving structured records for artifacts and tests.
    """

    def __init__(self, repository_tools: RepositoryTools) -> None:
        self.repository_tools = repository_tools
        self.calls: list[dict[str, object]] = []

    def _record(self, tool_name: str, args: dict[str, object], result: ToolResult) -> str:
        result_record = result.to_record()
        observation = json.dumps(result_record, ensure_ascii=True, sort_keys=True)

        self.calls.append(
            {
                "call_index": len(self.calls),
                "tool_name": tool_name,
                "args": args,
                "result": result_record,
                "observation_chars": len(observation),
                "observation_fingerprint": fingerprint(observation),
            }
        )
        return observation

    def search_repository(self, query: str) -> str:
        """Search files inside the bound repository."""

        return self._record(
            "search_repository",
            {"query": query},
            self.repository_tools.search_repository(query),
        )

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: int = 80,
    ) -> str:
        """Read a bounded range from a repository-relative file."""

        return self._record(
            "read_file",
            {"path": path, "start_line": start_line, "end_line": end_line},
            self.repository_tools.read_file(path, start_line, end_line),
        )

    def inspect_symbol(self, name: str) -> str:
        """Inspect a Python symbol inside the bound repository."""

        return self._record(
            "inspect_symbol",
            {"name": name},
            self.repository_tools.inspect_symbol(name),
        )
