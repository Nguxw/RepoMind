# RepoMind

RepoMind is a codebase understanding and LLM-Wiki generation platform. This first MVP implements the foundation: a FastAPI backend that imports a public GitHub repository, filters files safely, builds a file tree, and generates a structured `RepoProfile`.

This stage intentionally does not include LLM calls, Tree-sitter indexing, Wiki generation, or the frontend. Those modules are scaffolded in the project plan and will build on this ingestion layer.

## What Works Now

- Clone a public GitHub repository from a GitHub URL.
- Ignore noisy or unsafe content such as `.git`, `node_modules`, virtual environments, build outputs, binary files, and large files.
- Generate a file tree for included files.
- Detect languages, package managers, frameworks, README files, dependency files, config files, entrypoints, tests, important files, and important directories.
- Extract Python, JavaScript, and TypeScript symbols for classes, functions, methods, imports, and exports.
- Build a minimal RepoKG with Repository, Directory, File, Config, Dependency, Class, Function, and Method nodes.
- Store import metadata locally under `data/metadata`.
- Expose a small FastAPI API for import/profile/file-tree access.

## Project Layout

```text
apps/
  api/                         FastAPI backend
packages/
  repo_ingestion/              Clone, ignore, scan, detect, profile
  storage/                     Local MVP metadata storage
tests/                         Unit and API tests
```

## API

```text
GET  /health
POST /api/repos/import
GET  /api/repos/{repo_id}/profile
GET  /api/repos/{repo_id}/files
GET  /api/repos/{repo_id}/symbols
GET  /api/repos/{repo_id}/graph
```

Example import request:

```bash
curl -X POST http://localhost:8000/api/repos/import \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://github.com/pallets/flask\"}"
```

## Local Development

Create an environment and install dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
python -m pytest
```

Optional Tree-sitter parser support:

```bash
python -m pip install -e ".[parser]"
```

The symbol extractor will use Tree-sitter when language parsers are installed. Without them, the MVP falls back to Python AST and lightweight JavaScript/TypeScript parsing so the ingestion workflow remains runnable.

Start the API:

```bash
uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Open the health check:

```text
http://127.0.0.1:8000/health
```

## Docker

```bash
docker compose up --build
```

The API will be available at:

```text
http://127.0.0.1:8000
```

## Environment Variables

Copy `.env.example` to `.env` when you want local overrides.

```env
REPOMIND_DATA_DIR=./data
REPOMIND_MAX_FILE_BYTES=1048576
REPOMIND_CLONE_TIMEOUT_SECONDS=120
```

## Next Stages

1. Add `ModelGateway` with OpenAI-compatible and mock clients.
2. Implement `WikiEngine` with structured pages, citations, and Mermaid diagrams.
3. Build the Next.js workbench UI with Wiki, Evidence, Monaco, Mermaid, and Ask panels.
4. Add persistent PostgreSQL storage for profiles, symbols, graph edges, wiki pages, and traces.
