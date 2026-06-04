import pytest

from packages.repo_ingestion.clone import InvalidRepositoryUrl, validate_github_url


def test_validate_github_https_url_normalizes_to_clone_url():
    assert validate_github_url("https://github.com/openai/codex") == "https://github.com/openai/codex.git"


def test_validate_github_ssh_url_normalizes_to_https_clone_url():
    assert validate_github_url("git@github.com:openai/codex.git") == "https://github.com/openai/codex.git"


def test_validate_github_url_rejects_non_github_hosts():
    with pytest.raises(InvalidRepositoryUrl):
        validate_github_url("https://example.com/openai/codex")
