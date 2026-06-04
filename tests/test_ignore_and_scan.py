from pathlib import Path

from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.ignore import should_include_file


def test_scan_repository_ignores_cache_binary_and_large_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x00")
    (tmp_path / "large.txt").write_text("x" * 20, encoding="utf-8")

    assert should_include_file(tmp_path, tmp_path / "src" / "main.py", max_file_bytes=10_000)
    assert not should_include_file(tmp_path, tmp_path / "image.png", max_file_bytes=10_000)
    assert not should_include_file(tmp_path, tmp_path / "large.txt", max_file_bytes=10)

    scan = scan_repository(tmp_path, max_file_bytes=10_000)

    assert scan.included_files == ["src/main.py", "large.txt"] or scan.included_files == ["large.txt", "src/main.py"]
    assert "node_modules/ignored.js" not in scan.included_files
    assert "image.png" not in scan.included_files
