from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


GITHUB_HTTPS_RE = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
GITHUB_SSH_RE = re.compile(r"^git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?$")


class InvalidRepositoryUrl(ValueError):
    pass


class RepositoryCloneError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloneResult:
    repo_id: str
    local_path: str
    commit_sha: str
    normalized_url: str


def validate_github_url(url: str) -> str:
    candidate = url.strip()
    match = GITHUB_HTTPS_RE.match(candidate) or GITHUB_SSH_RE.match(candidate)
    if not match:
        raise InvalidRepositoryUrl("Only GitHub repository URLs are supported, for example https://github.com/owner/repo.")
    owner = match.group("owner")
    repo = match.group("repo")
    return f"https://github.com/{owner}/{repo}.git"


def clone_repository(url: str, destination_root: str | Path, timeout_seconds: int = 120) -> CloneResult:
    normalized_url = validate_github_url(url)
    repo_id = uuid.uuid4().hex
    destination_root = Path(destination_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    local_path = destination_root / repo_id

    command = ["git", "clone", "--depth", "1", normalized_url, str(local_path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    if result.returncode != 0:
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
        message = result.stderr.strip() or result.stdout.strip() or "git clone failed"
        raise RepositoryCloneError(message)

    commit_sha = _read_commit_sha(local_path)
    return CloneResult(
        repo_id=repo_id,
        local_path=str(local_path),
        commit_sha=commit_sha,
        normalized_url=normalized_url,
    )


def _read_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
