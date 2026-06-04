from __future__ import annotations

import os
from pathlib import Path

from packages.repo_ingestion.ignore import max_file_bytes_from_env, should_include_file, should_skip_dir
from packages.repo_ingestion.models import FileNode, RepositoryScan


def iter_included_files(root: Path, max_file_bytes: int | None = None) -> list[Path]:
    root = root.resolve()
    included: list[Path] = []
    max_bytes = max_file_bytes if max_file_bytes is not None else max_file_bytes_from_env()

    for current_root, dir_names, file_names in os.walk(root):
        current_path = Path(current_root)
        dir_names[:] = [
            dir_name for dir_name in sorted(dir_names)
            if not should_skip_dir((current_path / dir_name).relative_to(root))
        ]
        for file_name in sorted(file_names):
            file_path = current_path / file_name
            if should_include_file(root, file_path, max_bytes):
                included.append(file_path)

    return included


def build_file_tree(root: Path, included_files: list[Path]) -> FileNode:
    root = root.resolve()
    tree = FileNode(name=root.name, path="", type="directory")

    for file_path in sorted(included_files):
        relative = file_path.relative_to(root)
        cursor = tree
        accumulated: list[str] = []
        for part in relative.parts[:-1]:
            accumulated.append(part)
            directory_path = "/".join(accumulated)
            existing = next((child for child in cursor.children if child.type == "directory" and child.name == part), None)
            if existing is None:
                existing = FileNode(name=part, path=directory_path, type="directory")
                cursor.children.append(existing)
            cursor = existing
        cursor.children.append(
            FileNode(
                name=relative.name,
                path=relative.as_posix(),
                type="file",
                size=file_path.stat().st_size,
            )
        )

    _sort_tree(tree)
    return tree


def scan_repository(root: str | Path, max_file_bytes: int | None = None) -> RepositoryScan:
    root_path = Path(root).resolve()
    included_files = iter_included_files(root_path, max_file_bytes=max_file_bytes)
    total_bytes = sum(file_path.stat().st_size for file_path in included_files)
    return RepositoryScan(
        root_path=str(root_path),
        included_files=[file_path.relative_to(root_path).as_posix() for file_path in included_files],
        file_tree=build_file_tree(root_path, included_files),
        total_included_bytes=total_bytes,
    )


def _sort_tree(node: FileNode) -> None:
    node.children.sort(key=lambda child: (child.type != "directory", child.name.lower()))
    for child in node.children:
        if child.type == "directory":
            _sort_tree(child)
