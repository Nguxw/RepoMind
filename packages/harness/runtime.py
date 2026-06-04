from __future__ import annotations

import json

from packages.harness.state import AgentRun, AskAnswer, ToolCall
from packages.model_gateway.base import BaseModelClient
from packages.retrieval import retrieve_context
from packages.storage.repositories import RepositoryRecord
from packages.wiki_engine.generator import WikiGenerator


class AgentRuntime:
    def __init__(self, model_client: BaseModelClient) -> None:
        self.model_client = model_client

    async def generate_wiki(self, record: RepositoryRecord) -> tuple[list, AgentRun]:
        run = AgentRun(task="generate wiki", repo_id=record.repo_id, model=f"{self.model_client.provider}:{self.model_client.model}")
        generator = WikiGenerator(self.model_client)
        pages = await generator.generate(record.profile, _file_paths(record), record.symbols, record.graph_or_empty())
        run.steps.append(ToolCall(tool="wiki_planner", input={}, output=[page.title for page in pages]))
        for page in pages:
            run.steps.append(
                ToolCall(
                    tool="model_call",
                    input={"task": "generate_wiki_page", "page": page.title},
                    output={"provider": self.model_client.provider, "model": self.model_client.model, "summary_preview": page.summary[:300]},
                )
            )
        run.steps.append(ToolCall(tool="citation_checker", input={}, output=sum(len(page.invalid_citation_warnings) for page in pages)))
        run.output = {"wiki_pages": [page.model_dump(mode="json") for page in pages]}
        return pages, run

    async def ask(self, record: RepositoryRecord, question: str) -> tuple[AskAnswer, AgentRun]:
        run = AgentRun(task="ask wiki", repo_id=record.repo_id, model=f"{self.model_client.provider}:{self.model_client.model}")
        context = retrieve_context(record.profile, record.wiki_pages, record.symbols, question)
        run.steps.append(ToolCall(tool="retrieve_context", input={"question": question}, output=context.model_dump(mode="json")))
        answer_text = await self._generate_answer_text(question, context, run)
        answer = AskAnswer(question=question, answer=answer_text, citations=context.citations, run_id=run.run_id)
        run.output = answer.model_dump(mode="json")
        return answer, run

    async def _generate_answer_text(self, question: str, context, run: AgentRun) -> str:
        if not context.citations:
            return _grounded_answer(question, context)

        payload = {
            "question": question,
            "wiki_pages": [
                {
                    "title": page.title,
                    "summary": page.summary,
                    "sections": [{"heading": section.heading, "content": section.content} for section in page.sections[:3]],
                }
                for page in context.wiki_pages
            ],
            "symbols": [
                {
                    "name": symbol.name,
                    "type": symbol.type,
                    "file_path": symbol.file_path,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "signature": symbol.signature,
                }
                for symbol in context.symbols[:12]
            ],
            "snippets": [snippet.model_dump(mode="json") for snippet in context.snippets],
            "citations": [citation.model_dump(mode="json") for citation in context.citations],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer repository questions using only the provided wiki, symbols, snippets, and citations. "
                    "Do not invent files, symbols, modules, commands, or behavior. "
                    "If evidence is insufficient, say so briefly. Mention citation file paths in the answer."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            answer = await self.model_client.generate_text(messages)
        except Exception as exc:
            run.steps.append(ToolCall(tool="model_call", input={"task": "ask"}, output={"error": str(exc)}))
            return _grounded_answer(question, context)

        answer = answer.strip()
        run.steps.append(ToolCall(tool="model_call", input={"task": "ask"}, output={"provider": self.model_client.provider, "model": self.model_client.model, "preview": answer[:500]}))
        return answer or _grounded_answer(question, context)


def _file_paths(record: RepositoryRecord) -> list[str]:
    result: list[str] = []

    def visit(node) -> None:
        if node.type == "file":
            result.append(node.path)
        for child in node.children:
            visit(child)

    visit(record.file_tree)
    return result


def _grounded_answer(question: str, context) -> str:
    if not context.citations:
        return "I could not find enough repository evidence to answer that without guessing."
    page_titles = ", ".join(page.title for page in context.wiki_pages) or "the indexed source"
    symbol_names = ", ".join(f"`{symbol.name}`" for symbol in context.symbols[:5])
    evidence = "; ".join(f"{citation.file_path}:{citation.start_line}-{citation.end_line}" for citation in context.citations[:5])
    if symbol_names:
        return f"Based on {page_titles}, the relevant code appears around {symbol_names}. Evidence: {evidence}."
    return f"Based on {page_titles}, the repository evidence points to {evidence}."
