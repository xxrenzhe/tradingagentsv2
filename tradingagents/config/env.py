from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env(start: Path | None = None, *, override: bool = True) -> None:
    root = _find_project_root(start or Path.cwd())
    load_dotenv(root / ".env", override=override)
    load_dotenv(root / ".env.enterprise", override=override)


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / ".env").exists() or (candidate / ".env.example").exists() or (candidate / "pyproject.toml").exists():
            return candidate

    return current
