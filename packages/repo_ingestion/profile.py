from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from packages.repo_ingestion.clone import validate_github_url
from packages.repo_ingestion.manifests import (
    IMPORTANT_DIRECTORY_NAMES,
    LANGUAGE_BY_EXTENSION,
    is_config_file,
    is_dependency_file,
    is_entrypoint,
    is_readme,
    is_test_file,
)
from packages.repo_ingestion.models import RepoProfile, RepositoryScan


def build_repo_profile(
    repo_id: str,
    source_url: str,
    local_path: str | Path,
    scan: RepositoryScan,
    commit_sha: str | None = None,
) -> RepoProfile:
    root = Path(local_path).resolve()
    file_paths = sorted(scan.included_files)
    language_counts = _detect_language_counts(file_paths)
    readme_files = [path for path in file_paths if is_readme(path)]
    dependency_files = [path for path in file_paths if is_dependency_file(path)]
    config_files = [path for path in file_paths if is_config_file(path)]
    entrypoints = [path for path in file_paths if is_entrypoint(path)]
    test_files = [path for path in file_paths if is_test_file(path)]

    important_files = _unique_sorted([
        *readme_files,
        *dependency_files,
        *config_files,
        *entrypoints,
        *test_files[:20],
    ])[:60]

    return RepoProfile(
        repo_id=repo_id,
        name=_repo_name_from_url(source_url) or root.name,
        source_url=source_url,
        local_path=str(root),
        commit_sha=commit_sha or _read_commit_sha(root),
        description=_read_description(root, readme_files, dependency_files),
        languages=list(language_counts.keys()),
        frameworks=_detect_frameworks(root, dependency_files),
        package_managers=_detect_package_managers(dependency_files),
        readme_files=readme_files,
        dependency_files=dependency_files,
        config_files=config_files,
        entrypoints=entrypoints,
        test_files=test_files,
        important_files=important_files,
        important_directories=_detect_important_directories(file_paths),
        file_count=len(file_paths),
    )


def _repo_name_from_url(url: str) -> str | None:
    try:
        normalized = validate_github_url(url)
    except ValueError:
        return None
    return normalized.rstrip("/").removesuffix(".git").split("/")[-1]


def _detect_language_counts(file_paths: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in file_paths:
        language = LANGUAGE_BY_EXTENSION.get(Path(path).suffix.lower())
        if language:
            counts[language] += 1
    return dict(counts.most_common())


def _detect_package_managers(dependency_files: list[str]) -> list[str]:
    managers: set[str] = set()
    names = {Path(path).name for path in dependency_files}
    if {"requirements.txt", "requirements-dev.txt", "setup.py", "setup.cfg"} & names:
        managers.add("pip")
    if {"pyproject.toml", "poetry.lock"} & names:
        managers.add("poetry")
    if {"Pipfile", "Pipfile.lock"} & names:
        managers.add("pipenv")
    if {"environment.yml", "environment.yaml", "conda.yml", "conda.yaml"} & names:
        managers.add("conda")
    if "package.json" in names:
        managers.add("npm")
    if "pnpm-lock.yaml" in names:
        managers.add("pnpm")
    if "yarn.lock" in names:
        managers.add("yarn")
    return sorted(managers)


def _detect_frameworks(root: Path, dependency_files: list[str]) -> list[str]:
    text = "\n".join(_safe_read_text(root / path, limit=120_000).lower() for path in dependency_files)
    package_json = _read_package_json(root, dependency_files)
    frameworks: set[str] = set()

    keyword_map = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "pytorch": "PyTorch",
        "torch": "PyTorch",
        "tensorflow": "TensorFlow",
        "sklearn": "scikit-learn",
        "scikit-learn": "scikit-learn",
        "next": "Next.js",
        "next.js": "Next.js",
        "react": "React",
        "vue": "Vue",
        "svelte": "Svelte",
        "vite": "Vite",
        "express": "Express",
    }
    for keyword, framework in keyword_map.items():
        if keyword in text:
            frameworks.add(framework)

    dependencies = {
        **package_json.get("dependencies", {}),
        **package_json.get("devDependencies", {}),
    }
    npm_map = {
        "next": "Next.js",
        "react": "React",
        "vue": "Vue",
        "svelte": "Svelte",
        "vite": "Vite",
        "express": "Express",
    }
    for dependency, framework in npm_map.items():
        if dependency in dependencies:
            frameworks.add(framework)

    return sorted(frameworks)


def _detect_important_directories(file_paths: list[str]) -> list[str]:
    directories: set[str] = set()
    for path in file_paths:
        parts = Path(path).parts
        for part in parts[:-1]:
            if part in IMPORTANT_DIRECTORY_NAMES:
                directories.add(part)
    return sorted(directories)


def _read_description(root: Path, readme_files: list[str], dependency_files: list[str]) -> str | None:
    for readme in readme_files:
        summary = _first_readme_heading(root / readme)
        if summary:
            return summary

    package_json = _read_package_json(root, dependency_files)
    description = package_json.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return None


def _first_readme_heading(path: Path) -> str | None:
    text = _safe_read_text(path, limit=20_000)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.lstrip("#").strip() or None
    return None


def _read_package_json(root: Path, dependency_files: list[str]) -> dict:
    package_paths = [path for path in dependency_files if Path(path).name == "package.json"]
    if not package_paths:
        return {}
    try:
        return json.loads(_safe_read_text(root / package_paths[0], limit=120_000))
    except json.JSONDecodeError:
        return {}


def _read_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _safe_read_text(path: Path, limit: int) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(values))
