import pytest

from packages.code_intelligence.models import RepoGraph
from packages.model_gateway import MockModelClient
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile
from packages.code_intelligence.symbol_extractor import extract_symbols
from packages.wiki_engine.generator import WikiGenerator


@pytest.mark.asyncio
async def test_wiki_generator_creates_default_pages_with_citations(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\n\ndef create_app():\n    return FastAPI()\n", encoding="utf-8")
    scan = scan_repository(tmp_path)
    profile = build_repo_profile("repo-1", "https://github.com/example/demo.git", tmp_path, scan, "abc123")
    symbols = extract_symbols(tmp_path, scan.included_files)

    pages = await WikiGenerator(MockModelClient()).generate(profile, scan.included_files, symbols, RepoGraph(repo_id="repo-1"))

    titles = {page.title for page in pages}
    assert {"Overview", "Architecture", "Core Modules", "Important Files", "How to Run", "Reading Guide"} <= titles
    assert any(page.diagrams for page in pages)
    assert all(citation.status == "valid" for page in pages for section in page.sections for citation in section.citations)
