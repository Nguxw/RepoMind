from __future__ import annotations

import os

from packages.config import load_env_file


def test_load_env_file_sets_missing_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# RepoMind local config",
                "MODEL_PROVIDER=openai_compatible",
                "OPENAI_MODEL='mimo-v2.5-pro'",
                'OPENAI_BASE_URL="https://example.test/v1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    load_env_file(env_file)

    assert os.environ["MODEL_PROVIDER"] == "openai_compatible"
    assert os.environ["OPENAI_MODEL"] == "mimo-v2.5-pro"
    assert os.environ["OPENAI_BASE_URL"] == "https://example.test/v1"


def test_load_env_file_does_not_override_existing_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_PROVIDER=openai_compatible\n", encoding="utf-8")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")

    load_env_file(env_file)

    assert os.environ["MODEL_PROVIDER"] == "mock"
