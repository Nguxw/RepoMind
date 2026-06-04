"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Github, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function NewRepoPage() {
  const router = useRouter();
  const [url, setUrl] = useState("https://github.com/octocat/Hello-World");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/repos/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "Import failed");
      }
      const payload = await response.json();
      router.push(`/repos/${payload.repo_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-8 md:px-10">
      <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl content-center gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-5">
          <div className="inline-flex items-center gap-2 border border-ink bg-citrus px-3 py-1 text-sm font-semibold uppercase">
            <Github size={16} aria-hidden />
            RepoMind
          </div>
          <h1 className="max-w-2xl text-4xl font-black leading-tight md:text-6xl">
            Repository evidence workbench.
          </h1>
          <p className="max-w-xl text-lg leading-8 text-ink/72">
            Paste a public GitHub URL to start a RepoMind analysis run.
          </p>
        </div>

        <form onSubmit={submit} className="panel grid content-between gap-6 rounded-md p-5 md:p-7">
          <div>
            <label htmlFor="repo-url" className="text-sm font-bold uppercase text-ink/68">
              GitHub repository URL
            </label>
            <input
              id="repo-url"
              className="focus-ring mt-3 w-full border border-ink bg-white px-4 py-4 font-mono text-base"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://github.com/owner/repo"
            />
            {error ? <p className="mt-3 border-l-4 border-rust bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p> : null}
          </div>

          <button
            className="focus-ring inline-flex h-12 items-center justify-center gap-2 border border-ink bg-ink px-5 font-bold text-paper transition hover:bg-signal disabled:cursor-not-allowed disabled:opacity-70"
            disabled={loading}
            type="submit"
          >
            {loading ? <Loader2 className="animate-spin" size={18} aria-hidden /> : <ArrowRight size={18} aria-hidden />}
            Import Repository
          </button>
        </form>
      </section>
    </main>
  );
}
