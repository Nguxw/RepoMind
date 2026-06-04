"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Activity, Bot, Braces, FileCode2, GitBranch, Loader2, Network, RefreshCcw, Search, Send } from "lucide-react";
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent } from "../../../components/ui/card";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Tab = "overview" | "wiki" | "graph" | "ask";

type Citation = {
  file_path: string;
  start_line: number;
  end_line: number;
  status?: string;
  message?: string;
};

type WikiPage = {
  slug: string;
  title: string;
  summary: string;
  sections: { heading: string; content: string; citations: Citation[] }[];
  diagrams: { title: string; content: string }[];
  related_pages: string[];
  invalid_citation_warnings: string[];
};

type AskTurn = {
  id: string;
  question: string;
  answer?: string;
  citations: Citation[];
  run_id?: string;
  pending?: boolean;
  error?: string;
};

export default function RepoWorkbench({ repoId, initialTab }: { repoId: string; initialTab: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [profile, setProfile] = useState<any>(null);
  const [symbols, setSymbols] = useState<any[]>([]);
  const [graph, setGraph] = useState<any>(null);
  const [wiki, setWiki] = useState<WikiPage[]>([]);
  const [activeSlug, setActiveSlug] = useState("overview");
  const [source, setSource] = useState<{ path: string; content: string; citation?: Citation } | null>(null);
  const [question, setQuestion] = useState("");
  const [askTurns, setAskTurns] = useState<AskTurn[]>([]);
  const [wikiLoading, setWikiLoading] = useState(false);
  const [askLoading, setAskLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetchJson(`/api/repos/${repoId}/profile`),
      fetchJson(`/api/repos/${repoId}/symbols`),
      fetchJson(`/api/repos/${repoId}/graph`),
      fetchJson(`/api/repos/${repoId}/wiki`)
    ])
      .then(([profilePayload, symbolsPayload, graphPayload, wikiPayload]) => {
        setProfile(profilePayload.profile);
        setSymbols(symbolsPayload.symbols);
        setGraph(graphPayload.graph);
        setWiki(wikiPayload.pages);
      })
      .catch((err) => setError(String(err)));
  }, [repoId]);

  const activePage = useMemo(() => wiki.find((page) => page.slug === activeSlug) ?? wiki[0], [wiki, activeSlug]);

  async function generateWiki() {
    setWikiLoading(true);
    setError("");
    try {
      const payload = await fetchJson(`/api/repos/${repoId}/wiki/generate`, { method: "POST" });
      setWiki(payload.pages);
      if (payload.pages[0]) setActiveSlug(payload.pages[0].slug);
    } catch (err) {
      setError(String(err));
    } finally {
      setWikiLoading(false);
    }
  }

  async function openCitation(citation: Citation) {
    try {
      const payload = await fetchJson(`/api/repos/${repoId}/source?path=${encodeURIComponent(citation.file_path)}`);
      setSource({ path: citation.file_path, content: payload.content, citation });
    } catch (err) {
      setError(String(err));
    }
  }

  async function askRepo() {
    const submittedQuestion = question.trim();
    if (!submittedQuestion || askLoading) return;

    const turnId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setAskTurns((turns) => [
      ...turns,
      { id: turnId, question: submittedQuestion, citations: [], pending: true }
    ]);
    setQuestion("");
    setAskLoading(true);
    setError("");
    try {
      const payload = await fetchJson(`/api/repos/${repoId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: submittedQuestion })
      });
      setAskTurns((turns) => turns.map((turn) => turn.id === turnId
        ? {
            id: turn.id,
            question: turn.question,
            answer: payload.answer,
            citations: payload.citations ?? [],
            run_id: payload.run_id,
            pending: false
          }
        : turn
      ));
      if (payload.citations?.[0]) openCitation(payload.citations[0]);
    } catch (err) {
      const message = String(err);
      setError(message);
      setAskTurns((turns) => turns.map((turn) => turn.id === turnId
        ? { ...turn, pending: false, error: message }
        : turn
      ));
    } finally {
      setAskLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-3 py-3 md:px-5">
      <div className="grid min-h-[calc(100vh-1.5rem)] gap-3">
        <header className="panel flex flex-wrap items-center justify-between gap-3 rounded-md px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold uppercase text-ink/60">
              <Network size={16} aria-hidden />
              RepoMind Workbench
            </div>
            <h1 className="text-2xl font-black md:text-3xl">{profile?.name ?? "Repository"}</h1>
          </div>
          <nav className="flex flex-wrap gap-2">
            <TabButton active={tab === "overview"} onClick={() => setTab("overview")} icon={<Braces size={16} />}>Overview</TabButton>
            <TabButton active={tab === "wiki"} onClick={() => setTab("wiki")} icon={<FileCode2 size={16} />}>Wiki</TabButton>
            <TabButton active={tab === "graph"} onClick={() => setTab("graph")} icon={<GitBranch size={16} />}>Graph</TabButton>
            <TabButton active={tab === "ask"} onClick={() => setTab("ask")} icon={<Bot size={16} />}>Ask</TabButton>
          </nav>
        </header>

        {error ? <div className="border border-rust bg-rust/10 px-4 py-2 text-sm text-rust">{error}</div> : null}

        <section className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[300px_minmax(0,1fr)_minmax(420px,32vw)]">
          <aside className="panel min-h-[78vh] rounded-md p-3 xl:h-[calc(100vh-7.6rem)]">
            <Button
              onClick={generateWiki}
              className="mb-3 w-full"
              variant="signal"
              disabled={wikiLoading}
            >
              {wikiLoading ? <Loader2 className="animate-spin" size={16} /> : <RefreshCcw size={16} />}
              Generate Wiki
            </Button>
            <div className="space-y-2">
              {wiki.length ? wiki.map((page) => (
                <button
                  key={page.slug}
                  onClick={() => { setActiveSlug(page.slug); setTab("wiki"); }}
                  className={`focus-ring w-full border px-3 py-2 text-left text-sm font-bold ${activeSlug === page.slug ? "border-ink bg-ink text-paper" : "border-zincLine bg-white hover:border-ink"}`}
                >
                  {page.title}
                </button>
              )) : <p className="px-2 py-8 text-sm text-ink/60">No wiki pages.</p>}
            </div>
          </aside>

          <section className="panel min-h-[78vh] overflow-hidden rounded-md xl:h-[calc(100vh-7.6rem)]">
            {tab === "overview" ? <OverviewPanel profile={profile} symbols={symbols} graph={graph} /> : null}
            {tab === "wiki" ? <WikiPanel page={activePage} openCitation={openCitation} /> : null}
            {tab === "graph" ? <GraphPanel graph={graph} /> : null}
            {tab === "ask" ? (
              <AskPanel
                question={question}
                setQuestion={setQuestion}
                askRepo={askRepo}
                turns={askTurns}
                openCitation={openCitation}
                loading={askLoading}
                repoId={repoId}
              />
            ) : null}
          </section>

          <aside className="panel min-h-[78vh] rounded-md p-3 xl:h-[calc(100vh-7.6rem)]">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase text-ink/60">
              <Search size={16} aria-hidden />
              Evidence
            </div>
            {source ? (
              <div className="h-[calc(100%-2.25rem)] min-h-[68vh] overflow-hidden border border-zincLine bg-white">
                <div className="border-b border-zincLine bg-paper px-3 py-2 font-mono text-xs">
                  {source.path}:{source.citation?.start_line}-{source.citation?.end_line}
                </div>
                <MonacoEditor
                  height="100%"
                  language={languageFor(source.path)}
                  value={source.content}
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    lineNumbers: "on",
                    fontSize: 13,
                    scrollBeyondLastLine: false,
                    renderLineHighlight: "all"
                  }}
                />
              </div>
            ) : <p className="px-2 py-8 text-sm leading-7 text-ink/65">No evidence selected.</p>}
          </aside>
        </section>
      </div>
    </main>
  );
}

function OverviewPanel({ profile, symbols, graph }: { profile: any; symbols: any[]; graph: any }) {
  return (
    <div className="grid gap-4 p-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Files" value={String(profile?.file_count ?? 0)} />
        <Metric label="Languages" value={(profile?.languages ?? []).join(", ") || "none"} />
        <Metric label="Symbols" value={String(symbols.length)} />
        <Metric label="Graph edges" value={String(graph?.edges?.length ?? 0)} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <ListBlock title="Important files" items={profile?.important_files ?? []} />
        <ListBlock title="Entrypoints" items={profile?.entrypoints ?? []} />
        <ListBlock title="Frameworks" items={profile?.frameworks ?? []} />
        <ListBlock title="Package managers" items={profile?.package_managers ?? []} />
      </div>
    </div>
  );
}

function WikiPanel({ page, openCitation }: { page?: WikiPage; openCitation: (citation: Citation) => void }) {
  if (!page) return <div className="p-6 text-ink/60">Generate the wiki to inspect structured pages.</div>;
  return (
    <article className="h-full overflow-auto p-5">
      <h2 className="text-3xl font-black">{page.title}</h2>
      <p className="mt-2 max-w-3xl leading-7 text-ink/70">{page.summary}</p>
      {page.invalid_citation_warnings.length ? (
        <div className="mt-4 border border-rust bg-rust/10 p-3 text-sm text-rust">{page.invalid_citation_warnings.join("; ")}</div>
      ) : null}
      <div className="mt-5 space-y-5">
        {page.diagrams.map((diagram) => <MermaidBlock key={diagram.title} title={diagram.title} chart={diagram.content} />)}
        {page.sections.map((section) => (
          <section key={section.heading} className="border-t border-zincLine pt-4">
            <h3 className="text-xl font-black">{section.heading}</h3>
            <p className="mt-2 whitespace-pre-line leading-7">{section.content}</p>
            <CitationRow citations={section.citations} openCitation={openCitation} />
          </section>
        ))}
      </div>
    </article>
  );
}

function GraphPanel({ graph }: { graph: any }) {
  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];
  const flow = toFlow(nodes, edges);
  return (
    <div className="grid h-full gap-4 overflow-auto p-4">
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Nodes" value={String(nodes.length)} />
        <Metric label="Edges" value={String(edges.length)} />
        <Metric label="Calls" value={String(edges.filter((edge: any) => edge.type === "calls").length)} />
      </div>
      <div className="h-[460px] overflow-hidden border border-zincLine bg-white">
        <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView minZoom={0.2}>
          <MiniMap pannable zoomable />
          <Controls />
          <Background />
        </ReactFlow>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <ListBlock title="Nodes" items={nodes.slice(0, 80).map((node: any) => `${node.type}: ${node.name}`)} />
        <ListBlock title="Edges" items={edges.slice(0, 80).map((edge: any) => `${edge.source} --${edge.type}--> ${edge.target}`)} />
      </div>
    </div>
  );
}

function AskPanel({
  question,
  setQuestion,
  askRepo,
  turns,
  openCitation,
  loading,
  repoId
}: {
  question: string;
  setQuestion: (value: string) => void;
  askRepo: () => void;
  turns: AskTurn[];
  openCitation: (citation: Citation) => void;
  loading: boolean;
  repoId: string;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askRepo();
    }
  }

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto] gap-4 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-zincLine pb-3">
        <div>
          <h2 className="text-3xl font-black">Ask RepoMind</h2>
          <p className="mt-1 text-sm font-semibold text-ink/58">Grounded repository Q&A with persistent turns and citations.</p>
        </div>
        <Badge>{turns.length} turns</Badge>
      </header>

      <div className="min-h-0 overflow-auto pr-1">
        {turns.length ? (
          <div className="space-y-4">
            {turns.map((turn, index) => (
              <AskTurnBlock
                key={turn.id}
                turn={turn}
                index={index}
                repoId={repoId}
                openCitation={openCitation}
              />
            ))}
            <div ref={endRef} />
          </div>
        ) : (
          <div className="grid h-full min-h-[360px] place-items-center border border-dashed border-zincLine bg-white/55 p-6 text-center">
            <div className="max-w-xl">
              <Bot className="mx-auto mb-4 text-basin" size={34} aria-hidden />
              <h3 className="text-2xl font-black">Start a repository conversation.</h3>
              <p className="mt-2 text-sm leading-7 text-ink/62">
                Ask about entrypoints, reading order, modules, data flow, or architecture. Each answer stays in this thread and keeps its citations.
              </p>
            </div>
          </div>
        )}
      </div>

      <form
        className="grid gap-2 border-t border-zincLine pt-3"
        onSubmit={(event) => {
          event.preventDefault();
          askRepo();
        }}
      >
        <div className="flex min-h-24 gap-2">
          <textarea
            className="focus-ring min-h-24 flex-1 resize-none border border-zincLine bg-white p-3 leading-6"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a follow-up. Press Enter to send, Shift+Enter for a new line."
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="focus-ring inline-flex w-16 shrink-0 items-center justify-center border border-ink bg-ink text-paper transition hover:bg-signal disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Send question"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
          </button>
        </div>
      </form>
    </div>
  );
}

function AskTurnBlock({
  turn,
  index,
  repoId,
  openCitation
}: {
  turn: AskTurn;
  index: number;
  repoId: string;
  openCitation: (citation: Citation) => void;
}) {
  return (
    <section className="grid gap-3">
      <div className="ml-auto max-w-[78%] border border-ink bg-ink px-4 py-3 text-paper">
        <div className="mb-1 text-xs font-bold uppercase text-paper/55">Question {index + 1}</div>
        <p className="whitespace-pre-line leading-7">{turn.question}</p>
      </div>

      <div className="max-w-[88%] border border-zincLine bg-white p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase text-ink/52">
          <Bot size={15} aria-hidden />
          RepoMind
        </div>
        {turn.pending ? (
          <div className="flex items-center gap-2 text-sm font-bold text-basin">
            <Loader2 className="animate-spin" size={16} aria-hidden />
            Reading wiki, graph, symbols, and citations...
          </div>
        ) : null}
        {turn.error ? <p className="leading-7 text-rust">{turn.error}</p> : null}
        {turn.answer ? <p className="whitespace-pre-line leading-7">{turn.answer}</p> : null}
        <CitationRow citations={turn.citations} openCitation={openCitation} />
        {turn.run_id ? (
          <Link href={`/repos/${repoId}/trace/${turn.run_id}`} className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-basin">
            <Activity size={16} aria-hidden />
            View trace
          </Link>
        ) : null}
      </div>
    </section>
  );
}

function CitationRow({ citations, openCitation }: { citations: Citation[]; openCitation: (citation: Citation) => void }) {
  if (!citations.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citations.map((citation) => (
        <button
          key={`${citation.file_path}:${citation.start_line}:${citation.end_line}`}
          onClick={() => openCitation(citation)}
          className="focus-ring border border-basin bg-basin/10 px-2 py-1 font-mono text-xs text-basin hover:bg-basin hover:text-white"
        >
          {citation.file_path}:{citation.start_line}-{citation.end_line}
        </button>
      ))}
    </div>
  );
}

function MermaidBlock({ title, chart }: { title: string; chart: string }) {
  const [html, setHtml] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    import("mermaid")
      .then((mermaid) => {
        mermaid.default.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base" });
        return mermaid.default.render(`chart-${title.replace(/\W+/g, "-")}-${Math.random().toString(16).slice(2)}`, chart);
      })
      .then((result) => {
        if (active) setHtml(result.svg);
      })
      .catch((err) => {
        if (active) setError(String(err));
      });
    return () => { active = false; };
  }, [chart, title]);

  return (
    <div className="border border-zincLine bg-white p-3">
      <h3 className="mb-2 text-sm font-black uppercase text-ink/60">{title}</h3>
      {error ? <div className="text-sm text-rust">Mermaid render failed: {error}</div> : <div className="mermaid overflow-auto" dangerouslySetInnerHTML={{ __html: html }} />}
    </div>
  );
}

function TabButton({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: ReactNode; children: ReactNode }) {
  return (
    <Button onClick={onClick} variant={active ? "default" : "outline"}>
      {icon}
      {children}
    </Button>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card className="bg-white shadow-none">
      <CardContent>
      <div className="text-xs font-bold uppercase text-ink/50">{label}</div>
      <div className="mt-1 truncate text-lg font-black">{value}</div>
      </CardContent>
    </Card>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="border border-zincLine bg-white p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-black uppercase text-ink/60">{title} <Badge>{items.length}</Badge></h3>
      {items.length ? (
        <ul className="grid gap-2 text-sm">
          {items.slice(0, 14).map((item) => <li key={item} className="truncate font-mono">{item}</li>)}
        </ul>
      ) : <p className="text-sm text-ink/50">None detected</p>}
    </div>
  );
}

async function fetchJson(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function languageFor(path: string) {
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".js") || path.endsWith(".jsx")) return "javascript";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  return "plaintext";
}

function toFlow(rawNodes: any[], rawEdges: any[]): { nodes: Node[]; edges: Edge[] } {
  const selectedNodes = rawNodes.slice(0, 80);
  const columns = 5;
  const nodes: Node[] = selectedNodes.map((node, index) => ({
    id: node.id,
    position: { x: (index % columns) * 220, y: Math.floor(index / columns) * 110 },
    data: { label: `${node.type}: ${node.name}` },
    style: {
      border: "1px solid #22577a",
      borderRadius: 4,
      background: node.type === "Repository" ? "#d6e356" : node.type === "Dependency" ? "#f4f1e8" : "#ffffff",
      color: "#16181d",
      fontSize: 12,
      width: 190
    }
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges: Edge[] = rawEdges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .slice(0, 160)
    .map((edge, index) => ({
      id: `${edge.source}-${edge.type}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.type,
      animated: edge.type === "calls",
      type: "smoothstep"
    }));
  return { nodes, edges };
}
