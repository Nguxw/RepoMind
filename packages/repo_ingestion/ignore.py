from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MAX_FILE_BYTES = 1_048_576

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".nuxt",
    "coverage",
    "htmlcov",
    "target",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "package-lock.json.tmp",
}

BINARY_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".dmg",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".pyc",
    ".pyd",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}


def max_file_bytes_from_env() -> int:
    raw_value = os.getenv("REPOMIND_MAX_FILE_BYTES")
    if not raw_value:
        return DEFAULT_MAX_FILE_BYTES
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_MAX_FILE_BYTES


def path_has_ignored_part(path: Path | str) -> bool:
    parts = Path(path).parts
    return any(part in IGNORED_DIR_NAMES for part in parts)


def should_skip_dir(path: Path | str) -> bool:
    return Path(path).name in IGNORED_DIR_NAMES or path_has_ignored_part(path)


def looks_binary(path: Path, sample_size: int = 4096) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
    except OSError:
        return True
    return b"\0" in sample


def should_include_file(root: Path, file_path: Path, max_file_bytes: int | None = None) -> bool:
    max_bytes = max_file_bytes if max_file_bytes is not None else max_file_bytes_from_env()
    try:
        relative_path = file_path.relative_to(root)
    except ValueError:
        return False

    if path_has_ignored_part(relative_path):
        return False
    if file_path.name in IGNORED_FILE_NAMES:
        return False
    if not file_path.is_file():
        return False
    try:
        if file_path.stat().st_size > max_bytes:
            return False
    except OSError:
        return False
    return not looks_binary(file_path)
