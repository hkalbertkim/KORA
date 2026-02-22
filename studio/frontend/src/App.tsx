import { useEffect, useMemo, useRef, useState } from "react";
import MetroMap from "./components/MetroMap";
import MetricsPanel from "./components/MetricsPanel";

type DemoReport = {
  ok?: boolean;
  total_time_ms?: number;
  total_llm_calls?: number;
  tokens_in?: number;
  tokens_out?: number;
  estimated_cost_usd?: number;
  stage_counts?: Record<string, number>;
  [key: string]: unknown;
};

type TraceEvent = {
  station: string;
  t: number;
  route?: string;
};

type StationEvent = {
  stage: string;
  status: string;
  time_ms: number;
  skipped?: boolean;
  tokens_in?: number;
  tokens_out?: number;
  meta?: {
    stop_reason?: string;
    gate_retrieval_hit?: boolean;
    gate_retrieval_strategy?: string;
    gate_verifier_ok?: boolean;
    adapter?: string;
    model?: string;
  };
};

type SummaryEvent = {
  ok: boolean;
  total_time_ms: number;
  total_llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  estimated_cost_usd?: number;
};

type RunMode = "direct" | "kora";

type RunHistoryItem = {
  run_id: string;
  prompt: string;
  mode: RunMode;
  summary: DemoReport;
};

type StationMetric = {
  status?: string;
  time_ms?: number;
  skipped?: boolean;
  tokens_in?: number;
  tokens_out?: number;
};

type RecentStationEvent = {
  station: string;
  stage: string;
  status: string;
  time_ms: number;
  skipped?: boolean;
  tokens_in?: number;
  tokens_out?: number;
  meta?: {
    stop_reason?: string;
    gate_retrieval_hit?: boolean;
    gate_retrieval_strategy?: string;
    gate_verifier_ok?: boolean;
    adapter?: string;
    model?: string;
  };
};

type RetrievalSummary = {
  retrieval_hit_rate: number;
  retrieval_attempts: number;
  retrieval_hits: number;
  accepted_gate_retrieval_count: number;
  accepted_gate_verified_count: number;
  terminal_full: boolean;
  terminal_full_rate: number;
};

const STATIONS = ["Input", "Deterministic", "Decision", "Adapter", "Verify", "Output"];

export default function App() {
  const [prompt, setPrompt] = useState("Summarize this request path.");
  const [report, setReport] = useState<DemoReport>({});
  const [history, setHistory] = useState<RunHistoryItem[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [runSkippedLLM, setRunSkippedLLM] = useState(false);
  const [stationMetrics, setStationMetrics] = useState<Record<string, StationMetric>>({});
  const [recentStationEvents, setRecentStationEvents] = useState<RecentStationEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchHistory = async () => {
    try {
      const data = await fetch("/api/run_history").then((res) => res.json());
      if (Array.isArray(data)) {
        setHistory(data as RunHistoryItem[]);
      }
    } catch {
      setHistory([]);
    }
  };

  const stationIndexMap = useMemo(() => {
    const out: Record<string, number> = {};
    STATIONS.forEach((name, idx) => {
      out[name] = idx;
    });
    return out;
  }, []);

  const comparison = useMemo(() => {
    if (history.length < 2) {
      return null;
    }
    const first = history[0];
    const second = history[1];
    if (first.prompt !== second.prompt || first.mode === second.mode) {
      return null;
    }

    const direct = first.mode === "direct" ? first : second;
    const kora = first.mode === "kora" ? first : second;
    const directCost = Number(direct.summary.estimated_cost_usd ?? 0);
    const koraCost = Number(kora.summary.estimated_cost_usd ?? 0);
    const savingsPercent = directCost > 0 ? ((directCost - koraCost) / directCost) * 100 : 0;
    const tokensDiff = Number(direct.summary.tokens_out ?? 0) - Number(kora.summary.tokens_out ?? 0);
    const latencyDiff = Number(direct.summary.total_time_ms ?? 0) - Number(kora.summary.total_time_ms ?? 0);

    return {
      directCost,
      koraCost,
      savingsPercent,
      tokensDiff,
      latencyDiff
    };
  }, [history]);

  const retrievalSummary = useMemo<RetrievalSummary>(() => {
    const attempts = recentStationEvents.filter((event) => {
      const reason = event.meta?.stop_reason ?? "";
      return (
        typeof event.meta?.gate_retrieval_hit === "boolean" ||
        reason.startsWith("accepted_gate_") ||
        reason.startsWith("escalate_gate_")
      );
    });
    const hits = attempts.filter((event) => event.meta?.gate_retrieval_hit === true);
    const acceptedGateRetrievalCount = recentStationEvents.filter(
      (event) => event.meta?.stop_reason === "accepted_gate_retrieval"
    ).length;
    const acceptedGateVerifiedCount = recentStationEvents.filter(
      (event) => event.meta?.stop_reason === "accepted_gate_verified"
    ).length;
    const last = recentStationEvents.length > 0 ? recentStationEvents[recentStationEvents.length - 1] : null;
    const lastAdapter = last?.meta?.adapter ?? "";
    const anyFullAdapter = recentStationEvents.some((event) => {
      const adapter = event.meta?.adapter;
      return typeof adapter === "string" && adapter.endsWith(":full");
    });
    const terminalFull =
      anyFullAdapter || (typeof lastAdapter === "string" && lastAdapter.endsWith(":full"));
    return {
      retrieval_hit_rate: attempts.length > 0 ? hits.length / attempts.length : 0,
      retrieval_attempts: attempts.length,
      retrieval_hits: hits.length,
      accepted_gate_retrieval_count: acceptedGateRetrievalCount,
      accepted_gate_verified_count: acceptedGateVerifiedCount,
      terminal_full: terminalFull,
      terminal_full_rate: terminalFull ? 1 : 0
    };
  }, [recentStationEvents]);

  const runMode = async (mode: RunMode) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setPlaying(true);
    setActiveIndex(0);
    setTrace([]);
    setRunSkippedLLM(false);
    setStationMetrics({});
    setRecentStationEvents([]);
    setReport({});
    try {
      const runRes = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, mode, adapter: "mock" })
      });
      if (!runRes.ok) {
        throw new Error("run request failed");
      }
      const runData = (await runRes.json()) as { run_id?: string };
      if (!runData.run_id) {
        throw new Error("missing run_id");
      }

      const es = new EventSource(`/api/sse_run?run_id=${encodeURIComponent(runData.run_id)}`);
      eventSourceRef.current = es;

      es.addEventListener("station", (ev) => {
        try {
          const parsed = JSON.parse((ev as MessageEvent<string>).data) as StationEvent;
          if (parsed.stage.toUpperCase() === "ADAPTER" && parsed.skipped === true) {
            setRunSkippedLLM(true);
          }
          const station = stageToStation(parsed.stage, parsed.skipped === true);
          const meta = parsed.meta && typeof parsed.meta === "object" ? parsed.meta : undefined;
          setTrace((prev) => [...prev, { station, t: prev.length }]);
          setStationMetrics((prev) => ({
            ...prev,
            [station]: {
              status: parsed.status,
              time_ms: parsed.time_ms,
              skipped: parsed.skipped,
              tokens_in: parsed.tokens_in,
              tokens_out: parsed.tokens_out
            }
          }));
          setRecentStationEvents((prev) => {
            const next = [
              ...prev,
              {
                station,
                stage: parsed.stage,
                status: parsed.status,
                time_ms: parsed.time_ms,
                skipped: parsed.skipped,
                tokens_in: parsed.tokens_in,
                tokens_out: parsed.tokens_out,
                meta
              }
            ];
            return next.length > 200 ? next.slice(next.length - 200) : next;
          });
          const next = stationIndexMap[station];
          if (typeof next === "number") {
            setActiveIndex(next);
          }
        } catch {
          // Ignore malformed payloads in demo mode.
        }
      });

      es.addEventListener("summary", (ev) => {
        try {
          const parsed = JSON.parse((ev as MessageEvent<string>).data) as SummaryEvent;
          setReport((prev) => ({
            ...prev,
            ok: parsed.ok,
            total_time_ms: parsed.total_time_ms,
            total_llm_calls: parsed.total_llm_calls,
            tokens_in: parsed.tokens_in,
            tokens_out: parsed.tokens_out,
            estimated_cost_usd: parsed.estimated_cost_usd
          }));
        } catch {
          // Ignore malformed summary payloads in demo mode.
        }
      });

      es.addEventListener("done", () => {
        es.close();
        eventSourceRef.current = null;
        setPlaying(false);
        void fetchHistory();
      });

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        setPlaying(false);
      };
    } catch {
      setPlaying(false);
    }
  };

  useEffect(() => {
    void fetchHistory();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  return (
    <main className="page">
      <header className="header">
        <h1>KORA Studio v0</h1>
        <p>Execution Viewer Demo (Mac local scaffold)</p>
      </header>

      <section className="controls card">
        <label htmlFor="prompt">Input</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
        />
        <div className="button-row">
          <button onClick={() => void runMode("direct")} disabled={playing}>
            {playing ? "Running..." : "Run Direct"}
          </button>
          <button onClick={() => void runMode("kora")} disabled={playing}>
            {playing ? "Running..." : "Run KORA"}
          </button>
        </div>
      </section>

      <section className="viewer card">
        <MetroMap
          stations={STATIONS}
          activeIndex={activeIndex}
          stationMetrics={stationMetrics}
          runSkippedLLM={runSkippedLLM}
        />
        <div className="trace-note">
          {trace.length > 0 ? `Trace steps: ${trace.length}` : "No trace loaded yet."}
        </div>
      </section>

      <section className="card">
        <MetricsPanel report={report} retrievalSummary={retrievalSummary} recentStationEvents={recentStationEvents} />
      </section>

      {comparison && (
        <section className="card">
          <h2>Direct vs KORA (Latest Pair)</h2>
          <div className="comparison-grid">
            <MetricLite label="Direct Cost" value={comparison.directCost.toFixed(8)} />
            <MetricLite label="KORA Cost" value={comparison.koraCost.toFixed(8)} />
            <MetricLite label="Savings %" value={comparison.savingsPercent.toFixed(4)} />
            <MetricLite label="Tokens Out Diff" value={comparison.tokensDiff} />
            <MetricLite label="Latency Diff (ms)" value={comparison.latencyDiff} />
          </div>
        </section>
      )}
    </main>
  );
}

function stageToStation(stage: string, skipped: boolean): string {
  const key = stage.toUpperCase();
  if (key === "DETERMINISTIC") return "Deterministic";
  if (key === "ADAPTER") return skipped ? "Output" : "Adapter";
  if (key === "VERIFY") return "Verify";
  if (key === "BUDGET") return "Verify";
  if (key === "IR") return "Input";
  if (key === "SCHEDULER") return "Decision";
  return "Decision";
}

function MetricLite({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
