# RepoMind

RepoMind is a codebase understanding and LLM-Wiki generation platform. The current MVP imports a public GitHub repository, filters files safely, builds a file tree, extracts symbols, constructs a minimal RepoKG, generates structured Wiki pages with source citations, answers grounded questions, records agent traces, and exposes a Next.js workbench UI.

The MVP is deterministic by default through `MockModelClient`, so it runs without API keys. Real model providers can be enabled through `ModelGateway`.

## What Works Now

- Clone a public GitHub repository from a GitHub URL.
- Ignore noisy or unsafe content such as `.git`, `node_modules`, virtual environments, build outputs, binary files, and large files.
- Generate a file tree for included files.
- Detect languages, package managers, frameworks, README files, dependency files, config files, entrypoints, tests, important files, and important directories.
- Extract Python, JavaScript, and TypeScript symbols for classes, functions, methods, imports, and exports.
- Build a minimal RepoKG with Repository, Directory, File, Config, Dependency, Class, Function, and Method nodes.
- Generate structured Wiki pages for Overview, Architecture, Core Modules, Important Files, How to Run, and Reading Guide.
- Validate source citations and expose source file content for citation panels.
- Ask questions over Wiki pages, symbols, graph evidence, and source snippets.
- Record trace data for Wiki generation and Ask runs.
- Store import metadata locally or in PostgreSQL through a SQLAlchemy-backed store.
- Record normalized rows for repositories, files, symbols, edges, wiki pages, wiki citations, agent runs, and tool calls.
- Run Wiki generation through a task queue abstraction with inline and Redis/Arq modes.
- Use in-memory vector retrieval by default, with a Qdrant adapter and Docker service available for later remote vector indexing.
- Use a Next.js workbench with Wiki, React Flow Graph, Ask, Evidence, Monaco, Mermaid, and shadcn-style UI components.
- Expose FastAPI APIs for import, profile, files, symbols, graph, Wiki, source, Ask, and trace access.

## Project Layout

```text
apps/
  api/                         FastAPI backend
  web/                         Next.js workbench frontend
packages/
  repo_ingestion/              Clone, ignore, scan, detect, profile
  code_intelligence/           Symbol extraction and RepoKG builder
  model_gateway/               OpenAI-compatible, OpenAI, Claude, DeepSeek, mock clients
  wiki_engine/                 Structured Wiki generation, citations, Mermaid
  retrieval/                   Wiki/symbol/source context packing
  harness/                     Lightweight AgentRuntime and trace state
  storage/                     File and SQLAlchemy/PostgreSQL metadata storage
  tasks/                       Inline and Redis/Arq queue adapters
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
GET  /api/repos/{repo_id}/source?path=...
POST /api/repos/{repo_id}/wiki/generate
GET  /api/repos/{repo_id}/wiki
GET  /api/repos/{repo_id}/wiki/{page_slug}
POST /api/repos/{repo_id}/ask
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/trace
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

Run a live LLM smoke test after setting model environment variables:

```bash
python scripts/live_llm_smoke.py
python scripts/live_api_smoke.py
python scripts/tree_sitter_smoke.py
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

Run the frontend when Node/npm is available:

```bash
cd apps/web
npm install
npm run dev
```

Open the health check:

```text
http://127.0.0.1:8000/health
```

## Docker

```bash
docker compose up --build
```

The app will be available at:

```text
http://127.0.0.1:3000
http://127.0.0.1:8000
postgres://127.0.0.1:5432
redis://127.0.0.1:6379
http://127.0.0.1:6333
```

Demo workflow:

1. Open `http://127.0.0.1:3000/repos/new`.
2. Import a public GitHub repository URL.
3. Open the generated workbench.
4. Click `Generate Wiki`.
5. Open citations in the Evidence panel.
6. Ask a repository question and inspect the linked trace.

## Environment Variables

Copy `.env.example` to `.env` when you want local overrides.

```env
REPOMIND_DATA_DIR=./data
REPOMIND_MAX_FILE_BYTES=1048576
REPOMIND_CLONE_TIMEOUT_SECONDS=120
REPOMIND_STORAGE=file
DATABASE_URL=postgresql+psycopg://repomind:repomind@postgres:5432/repomind
REPOMIND_QUEUE_MODE=inline
REDIS_URL=redis://redis:6379/0
REPOMIND_VECTOR_STORE=memory
QDRANT_URL=http://qdrant:6333

MODEL_PROVIDER=mock
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-5

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

## Next Stages

1. Move long-running import/wiki jobs fully to durable Redis/Arq background execution with polling-first UI.
2. Enable remote Qdrant writes with production embeddings.
3. Add richer Mermaid validation and graph layout controls.
4. Add authentication and private repository import.
