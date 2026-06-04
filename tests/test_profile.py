from pathlib import Path

from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile


def test_build_repo_profile_detects_project_shape(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "README.md").write_text("# Demo API\n\nExample project.\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\npytest\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "src" / "main.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
    (tmp_path / "tests" / "test_main.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    scan = scan_repository(tmp_path)
    profile = build_repo_profile(
        repo_id="repo-1",
        source_url="https://github.com/example/demo",
        local_path=tmp_path,
        scan=scan,
        commit_sha="abc123",
    )

    assert profile.name == "demo"
    assert profile.description == "Demo API"
    assert profile.languages == ["Python"]
    assert "FastAPI" in profile.frameworks
    assert "pip" in profile.package_managers
    assert "poetry" in profile.package_managers
    assert "README.md" in profile.readme_files
    assert "src/main.py" in profile.entrypoints
    assert "tests/test_main.py" in profile.test_files
    assert "src" in profile.important_directories
    assert profile.commit_sha == "abc123"
