from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.code_intelligence import build_repo_graph, extract_symbols
from packages.harness.runtime import AgentRuntime
from packages.model_gateway import create_model_client
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile
from packages.storage.repositories import RepositoryRecord


async def main() -> None:
    client = create_model_client()
    text = await client.generate_text([{"role": "user", "content": "Reply with exactly: repomind-live-ok"}])
    json_payload = await client.generate_json(
        [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": "Return a JSON object with status set to ok and project set to RepoMind."},
        ],
        schema={},
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        (repo_root / "README.md").write_text("# Live Demo\n\nA FastAPI demo repository.\n", encoding="utf-8")
        (repo_root / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
        (repo_root / "main.py").write_text(
            "from fastapi import FastAPI\n\n"
            "def create_app():\n"
            "    app = FastAPI()\n"
            "    return app\n",
            encoding="utf-8",
        )
        scan = scan_repository(repo_root)
        profile = build_repo_profile("live-repo", "https://github.com/example/live-demo.git", repo_root, scan, "live123")
        symbols = extract_symbols(repo_root, scan.included_files)
        graph = build_repo_graph("live-repo", profile, scan.included_files, symbols)
        record = RepositoryRecord(
            repo_id="live-repo",
            source_url=profile.source_url,
            local_path=str(repo_root),
            profile=profile,
            file_tree=scan.file_tree,
            symbols=symbols,
            graph=graph,
        )
        runtime = AgentRuntime(client)
        pages, wiki_run = await runtime.generate_wiki(record)
        record.wiki_pages = pages
        answer, ask_run = await runtime.ask(record, "Where is the FastAPI app created?")

    print(
        {
            "provider": client.provider,
            "model": client.model,
            "text_ok": "repomind-live-ok" in text,
            "json_keys": sorted(json_payload.keys()),
            "wiki_pages": len(pages),
            "first_page": pages[0].title if pages else None,
            "ask_has_citations": bool(answer.citations),
            "wiki_run_steps": len(wiki_run.steps),
            "ask_run_steps": len(ask_run.steps),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
