"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function TracePage({ params }: { params: { id: string; run_id: string } }) {
  const [run, setRun] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/runs/${params.run_id}/trace`)
      .then((response) => response.ok ? response.json() : response.json().then((payload) => Promise.reject(payload.detail)))
      .then((payload) => setRun(payload.run))
      .catch((err) => setError(String(err)));
  }, [params.run_id]);

  return (
    <main className="min-h-screen px-5 py-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <Link href={`/repos/${params.id}`} className="inline-flex items-center gap-2 text-sm font-bold text-basin">
          <ArrowLeft size={16} aria-hidden />
          Back to workbench
        </Link>
        <section className="panel rounded-md p-5">
          <div className="mb-4 flex items-center gap-2">
            <Activity size={18} aria-hidden />
            <h1 className="text-2xl font-black">Agent Trace</h1>
          </div>
          {error ? <p className="text-rust">{error}</p> : null}
          {!run && !error ? <p>Loading trace...</p> : null}
          {run ? (
            <div className="space-y-4">
              <div className="grid gap-3 text-sm md:grid-cols-4">
                <Metric label="Run" value={run.run_id} />
                <Metric label="Task" value={run.task} />
                <Metric label="Model" value={run.model} />
                <Metric label="Status" value={run.status} />
              </div>
              <pre className="max-h-[70vh] overflow-auto border border-zincLine bg-white p-4 font-mono text-xs leading-6">
                {JSON.stringify(run, null, 2)}
              </pre>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-zincLine bg-white p-3">
      <div className="text-xs font-bold uppercase text-ink/50">{label}</div>
      <div className="truncate font-mono text-sm">{value}</div>
    </div>
  );
}
