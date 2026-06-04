import pytest

from packages.repo_ingestion.clone import (
    CloneAttempt,
    InvalidRepositoryUrl,
    _clone_attempts,
    _clone_env,
    parse_github_url,
    validate_github_url,
)


def test_validate_github_https_url_normalizes_to_clone_url():
    assert validate_github_url("https://github.com/openai/codex") == "https://github.com/openai/codex.git"


def test_validate_github_ssh_url_normalizes_to_https_clone_url():
    assert validate_github_url("git@github.com:openai/codex.git") == "https://github.com/openai/codex.git"


def test_validate_github_url_rejects_non_github_hosts():
    with pytest.raises(InvalidRepositoryUrl):
        validate_github_url("https://example.com/openai/codex")


def test_parse_github_url_exposes_https_and_ssh_clone_urls():
    repository = parse_github_url("https://github.com/Nguxw/Mini_Hermes")

    assert repository.owner == "Nguxw"
    assert repository.repo == "Mini_Hermes"
    assert repository.https_url == "https://github.com/Nguxw/Mini_Hermes.git"
    assert repository.ssh_url == "git@github.com:Nguxw/Mini_Hermes.git"


def test_clone_attempts_default_to_https_then_ssh(monkeypatch):
    monkeypatch.delenv("REPOMIND_GIT_CLONE_STRATEGY", raising=False)
    monkeypatch.delenv("REPOMIND_GITHUB_MIRROR", raising=False)
    monkeypatch.delenv("REPOMIND_GITHUB_SSH_FALLBACK", raising=False)
    repository = parse_github_url("https://github.com/openai/codex")

    attempts = _clone_attempts(repository)

    assert [(attempt.label, attempt.url) for attempt in attempts] == [
        ("https", "https://github.com/openai/codex.git"),
        ("ssh", "git@github.com:openai/codex.git"),
    ]


def test_clone_attempts_can_use_ssh_first(monkeypatch):
    monkeypatch.setenv("REPOMIND_GIT_CLONE_STRATEGY", "ssh-first")
    repository = parse_github_url("https://github.com/openai/codex")

    attempts = _clone_attempts(repository)

    assert [attempt.label for attempt in attempts] == ["ssh", "https"]


def test_clone_env_adds_proxy_and_noninteractive_ssh(monkeypatch):
    monkeypatch.setenv("REPOMIND_GIT_PROXY", "http://127.0.0.1:7890")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    env = _clone_env(CloneAttempt("ssh", "git@github.com:openai/codex.git", ssh=True))

    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["HTTP_PROXY"] == "http://127.0.0.1:7890"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7890"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]
