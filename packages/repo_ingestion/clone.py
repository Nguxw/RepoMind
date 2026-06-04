from __future__ import annotations

import re
import os
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


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    repo: str

    @property
    def https_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}.git"

    @property
    def ssh_url(self) -> str:
        return f"git@github.com:{self.owner}/{self.repo}.git"


@dataclass(frozen=True)
class CloneAttempt:
    label: str
    url: str
    ssh: bool = False


def validate_github_url(url: str) -> str:
    return parse_github_url(url).https_url


def parse_github_url(url: str) -> GitHubRepository:
    candidate = url.strip()
    match = GITHUB_HTTPS_RE.match(candidate) or GITHUB_SSH_RE.match(candidate)
    if not match:
        raise InvalidRepositoryUrl("Only GitHub repository URLs are supported, for example https://github.com/owner/repo.")
    owner = match.group("owner")
    repo = match.group("repo")
    return GitHubRepository(owner=owner, repo=repo)


def clone_repository(url: str, destination_root: str | Path, timeout_seconds: int = 120) -> CloneResult:
    repository = parse_github_url(url)
    normalized_url = repository.https_url
    repo_id = uuid.uuid4().hex
    destination_root = Path(destination_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    local_path = destination_root / repo_id

    errors: list[tuple[str, str]] = []
    for attempt in _clone_attempts(repository):
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
        command = ["git", "clone", "--depth", "1", attempt.url, str(local_path)]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=_clone_env(attempt),
            )
        except subprocess.TimeoutExpired:
            errors.append((attempt.label, f"timed out after {timeout_seconds} seconds"))
            continue
        if result.returncode == 0:
            commit_sha = _read_commit_sha(local_path)
            return CloneResult(
                repo_id=repo_id,
                local_path=str(local_path),
                commit_sha=commit_sha,
                normalized_url=normalized_url,
            )
        message = result.stderr.strip() or result.stdout.strip() or "git clone failed"
        errors.append((attempt.label, message))

    if local_path.exists():
        shutil.rmtree(local_path, ignore_errors=True)
    raise RepositoryCloneError(_format_clone_failure(repository, errors))


def _clone_attempts(repository: GitHubRepository) -> list[CloneAttempt]:
    strategy = os.getenv("REPOMIND_GIT_CLONE_STRATEGY", "auto").strip().lower()
    ssh_fallback = _env_bool("REPOMIND_GITHUB_SSH_FALLBACK", default=True)
    attempts: list[CloneAttempt] = []

    if strategy in {"ssh", "ssh-only"}:
        attempts.append(CloneAttempt("ssh", repository.ssh_url, ssh=True))
    elif strategy in {"ssh-first", "ssh_first"}:
        attempts.append(CloneAttempt("ssh", repository.ssh_url, ssh=True))
        attempts.append(CloneAttempt("https", repository.https_url))
    else:
        attempts.append(CloneAttempt("https", repository.https_url))
        mirror_url = _mirror_url(repository)
        if mirror_url:
            attempts.append(CloneAttempt("mirror", mirror_url))
        if ssh_fallback and strategy not in {"https", "https-only"}:
            attempts.append(CloneAttempt("ssh", repository.ssh_url, ssh=True))

    deduped: list[CloneAttempt] = []
    seen: set[str] = set()
    for attempt in attempts:
        if attempt.url not in seen:
            deduped.append(attempt)
            seen.add(attempt.url)
    return deduped


def _mirror_url(repository: GitHubRepository) -> str:
    mirror = os.getenv("REPOMIND_GITHUB_MIRROR", "").strip()
    if not mirror:
        return ""
    if "{" in mirror:
        return mirror.format(
            owner=repository.owner,
            repo=repository.repo,
            url=repository.https_url,
            https_url=repository.https_url,
        )
    return f"{mirror.rstrip('/')}/{repository.https_url}"


def _clone_env(attempt: CloneAttempt) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    proxy = os.getenv("REPOMIND_GIT_PROXY", "").strip()
    if proxy:
        env.setdefault("HTTP_PROXY", proxy)
        env.setdefault("HTTPS_PROXY", proxy)
        env.setdefault("http_proxy", proxy)
        env.setdefault("https_proxy", proxy)

    if attempt.ssh:
        env["GIT_SSH_COMMAND"] = (
            os.getenv("REPOMIND_GIT_SSH_COMMAND", "").strip()
            or "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
        )
    return env


def _format_clone_failure(repository: GitHubRepository, errors: list[tuple[str, str]]) -> str:
    labels = ", ".join(label for label, _ in errors) or "none"
    lines = [
        f"Could not clone {repository.https_url}. Tried: {labels}.",
        "If GitHub HTTPS is blocked on this machine, set REPOMIND_GIT_CLONE_STRATEGY=ssh-first in .env.",
        "If you use a proxy, set REPOMIND_GIT_PROXY=http://host:port in .env.",
    ]
    if errors:
        lines.append("Clone errors:")
    for label, message in errors:
        lines.append(f"- {label}: {_compact_error(message)}")
    return "\n".join(lines)


def _compact_error(message: str, limit: int = 600) -> str:
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _read_commit_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
