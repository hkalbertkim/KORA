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

type WarmDemoRuns = {
  baseline_run_id: string;
  warmed_run_id: string;
};

type DemoRunState = {
  run_id: string | null;
  recentStationEvents: RecentStationEvent[];
  report: DemoReport;
};

const EMPTY_RUN_STATE: DemoRunState = {
  run_id: null,
  recentStationEvents: [],
  report: {}
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
  const [warmDemoRuns, setWarmDemoRuns] = useState<WarmDemoRuns | null>(null);
  const [baselineRun, setBaselineRun] = useState<DemoRunState>(EMPTY_RUN_STATE);
  const [warmedRun, setWarmedRun] = useState<DemoRunState>(EMPTY_RUN_STATE);
  const [activeRunLabel, setActiveRunLabel] = useState<string>("none");
  const eventSourceRef = useRef<EventSource | null>(null);
  const demoEventSourceRefs = useRef<{ baseline: EventSource | null; warmed: EventSource | null }>({
    baseline: null,
    warmed: null
  });
  const demoPendingCountRef = useRef(0);

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

  const retrievalSummary = useMemo<RetrievalSummary>(
    () => computeRetrievalSummary(recentStationEvents),
    [recentStationEvents]
  );
  const baselineRetrievalSummary = useMemo<RetrievalSummary>(
    () => computeRetrievalSummary(baselineRun.recentStationEvents),
    [baselineRun.recentStationEvents]
  );
  const warmedRetrievalSummary = useMemo<RetrievalSummary>(
    () => computeRetrievalSummary(warmedRun.recentStationEvents),
    [warmedRun.recentStationEvents]
  );

  const closeComparisonStreams = () => {
    if (demoEventSourceRefs.current.baseline) {
      demoEventSourceRefs.current.baseline.close();
      demoEventSourceRefs.current.baseline = null;
    }
    if (demoEventSourceRefs.current.warmed) {
      demoEventSourceRefs.current.warmed.close();
      demoEventSourceRefs.current.warmed = null;
    }
    demoPendingCountRef.current = 0;
  };

  const streamRun = async (runId: string, runLabel: string) => {
    closeComparisonStreams();
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setPlaying(true);
    setActiveRunLabel(runLabel);
    setActiveIndex(0);
    setTrace([]);
    setRunSkippedLLM(false);
    setStationMetrics({});
    setRecentStationEvents([]);
    setReport({});
    const es = new EventSource(`/api/sse_run?run_id=${encodeURIComponent(runId)}`);
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
  };

  const streamComparisonRun = (target: "baseline" | "warmed", runId: string) => {
    const existing = demoEventSourceRefs.current[target];
    if (existing) {
      existing.close();
      demoEventSourceRefs.current[target] = null;
    }
    const es = new EventSource(`/api/sse_run?run_id=${encodeURIComponent(runId)}`);
    demoEventSourceRefs.current[target] = es;
    let finalized = false;

    const setRunState =
      target === "baseline"
        ? setBaselineRun
        : setWarmedRun;

    es.addEventListener("station", (ev) => {
      try {
        const parsed = JSON.parse((ev as MessageEvent<string>).data) as StationEvent;
        const station = stageToStation(parsed.stage, parsed.skipped === true);
        const meta = parsed.meta && typeof parsed.meta === "object" ? parsed.meta : undefined;
        setRunState((prev) => {
          const nextEvents = [
            ...prev.recentStationEvents,
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
          return {
            ...prev,
            recentStationEvents: nextEvents.length > 200 ? nextEvents.slice(nextEvents.length - 200) : nextEvents
          };
        });
      } catch {
        // Ignore malformed payloads in demo mode.
      }
    });

    es.addEventListener("summary", (ev) => {
      try {
        const parsed = JSON.parse((ev as MessageEvent<string>).data) as SummaryEvent;
        setRunState((prev) => ({
          ...prev,
          report: {
            ...prev.report,
            ok: parsed.ok,
            total_time_ms: parsed.total_time_ms,
            total_llm_calls: parsed.total_llm_calls,
            tokens_in: parsed.tokens_in,
            tokens_out: parsed.tokens_out,
            estimated_cost_usd: parsed.estimated_cost_usd
          }
        }));
      } catch {
        // Ignore malformed summary payloads in demo mode.
      }
    });

    const finalize = () => {
      if (finalized) return;
      finalized = true;
      es.close();
      if (demoEventSourceRefs.current[target] === es) {
        demoEventSourceRefs.current[target] = null;
      }
      demoPendingCountRef.current = Math.max(0, demoPendingCountRef.current - 1);
      if (demoPendingCountRef.current === 0) {
        setPlaying(false);
        void fetchHistory();
      }
    };

    es.addEventListener("done", finalize);
    es.onerror = finalize;
  };

  const runMode = async (mode: RunMode) => {
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
      setWarmDemoRuns(null);
      setBaselineRun({ run_id: null, recentStationEvents: [], report: {} });
      setWarmedRun({ run_id: null, recentStationEvents: [], report: {} });
      await streamRun(runData.run_id, mode);
    } catch {
      setPlaying(false);
    }
  };

  const runRetrievalWarmDemo = async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    closeComparisonStreams();
    setPlaying(true);
    try {
      const runRes = await fetch("/api/run_retrieval_warm_demo", { method: "POST" });
      if (!runRes.ok) {
        throw new Error("warm demo request failed");
      }
      const data = (await runRes.json()) as WarmDemoRuns;
      if (!data.baseline_run_id || !data.warmed_run_id) {
        throw new Error("warm demo run ids missing");
      }
      setWarmDemoRuns(data);
      setActiveRunLabel("compare");
      setBaselineRun({
        run_id: data.baseline_run_id,
        recentStationEvents: [],
        report: {}
      });
      setWarmedRun({
        run_id: data.warmed_run_id,
        recentStationEvents: [],
        report: {}
      });
      demoPendingCountRef.current = 2;
      streamComparisonRun("baseline", data.baseline_run_id);
      streamComparisonRun("warmed", data.warmed_run_id);
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
      closeComparisonStreams();
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
          <button onClick={() => void runRetrievalWarmDemo()} disabled={playing}>
            {playing ? "Running..." : "Run Retrieval Warm Demo"}
          </button>
        </div>
        {warmDemoRuns && (
          <div className="button-row">
            <button onClick={() => void streamRun(warmDemoRuns.baseline_run_id, "baseline")} disabled={playing}>
              View Baseline
            </button>
            <button onClick={() => void streamRun(warmDemoRuns.warmed_run_id, "warmed")} disabled={playing}>
              View Warmed
            </button>
          </div>
        )}
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
        <div className="trace-note">Active run: {activeRunLabel}</div>
        <MetricsPanel report={report} retrievalSummary={retrievalSummary} recentStationEvents={recentStationEvents} />
      </section>

      {warmDemoRuns && (
        <section className="card">
          <h2>Retrieval Warm Compare</h2>
          <table>
            <thead>
              <tr>
                <th>metric</th>
                <th>baseline</th>
                <th>warmed</th>
                <th>delta</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>retrieval_hit_rate</td>
                <td>
                  {formatRateWithCount(
                    baselineRetrievalSummary.retrieval_hit_rate,
                    baselineRetrievalSummary.retrieval_hits,
                    baselineRetrievalSummary.retrieval_attempts
                  )}
                </td>
                <td>
                  {formatRateWithCount(
                    warmedRetrievalSummary.retrieval_hit_rate,
                    warmedRetrievalSummary.retrieval_hits,
                    warmedRetrievalSummary.retrieval_attempts
                  )}
                </td>
                <td>
                  {formatSignedPercent(
                    warmedRetrievalSummary.retrieval_hit_rate - baselineRetrievalSummary.retrieval_hit_rate
                  )}
                </td>
              </tr>
              <tr>
                <td>accepted_gate_retrieval_count</td>
                <td>{baselineRetrievalSummary.accepted_gate_retrieval_count}</td>
                <td>{warmedRetrievalSummary.accepted_gate_retrieval_count}</td>
                <td>
                  {warmedRetrievalSummary.accepted_gate_retrieval_count -
                    baselineRetrievalSummary.accepted_gate_retrieval_count}
                </td>
              </tr>
              <tr>
                <td>accepted_gate_verified_count</td>
                <td>{baselineRetrievalSummary.accepted_gate_verified_count}</td>
                <td>{warmedRetrievalSummary.accepted_gate_verified_count}</td>
                <td>
                  {warmedRetrievalSummary.accepted_gate_verified_count -
                    baselineRetrievalSummary.accepted_gate_verified_count}
                </td>
              </tr>
              <tr>
                <td>terminal_full</td>
                <td>{baselineRetrievalSummary.terminal_full ? "yes" : "no"}</td>
                <td>{warmedRetrievalSummary.terminal_full ? "yes" : "no"}</td>
                <td>
                  {baselineRetrievalSummary.terminal_full ? "yes" : "no"} -&gt;{" "}
                  {warmedRetrievalSummary.terminal_full ? "yes" : "no"}
                </td>
              </tr>
              <tr>
                <td>terminal_full_rate</td>
                <td>{baselineRetrievalSummary.terminal_full_rate}</td>
                <td>{warmedRetrievalSummary.terminal_full_rate}</td>
                <td>
                  {warmedRetrievalSummary.terminal_full_rate - baselineRetrievalSummary.terminal_full_rate}
                </td>
              </tr>
              <tr>
                <td>total_time_ms</td>
                <td>{baselineRun.report.total_time_ms ?? "-"}</td>
                <td>{warmedRun.report.total_time_ms ?? "-"}</td>
                <td>
                  {formatSignedNumber(
                    (warmedRun.report.total_time_ms as number | undefined) ?? null,
                    (baselineRun.report.total_time_ms as number | undefined) ?? null
                  )}
                </td>
              </tr>
              <tr>
                <td>tokens_out</td>
                <td>{baselineRun.report.tokens_out ?? "-"}</td>
                <td>{warmedRun.report.tokens_out ?? "-"}</td>
                <td>
                  {formatSignedNumber(
                    (warmedRun.report.tokens_out as number | undefined) ?? null,
                    (baselineRun.report.tokens_out as number | undefined) ?? null
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

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

function computeRetrievalSummary(events: RecentStationEvent[]): RetrievalSummary {
  const attempts = events.filter((event) => {
    const reason = event.meta?.stop_reason ?? "";
    return (
      typeof event.meta?.gate_retrieval_hit === "boolean" ||
      reason.startsWith("accepted_gate_") ||
      reason.startsWith("escalate_gate_")
    );
  });
  const hits = attempts.filter((event) => event.meta?.gate_retrieval_hit === true);
  const acceptedGateRetrievalCount = events.filter(
    (event) => event.meta?.stop_reason === "accepted_gate_retrieval"
  ).length;
  const acceptedGateVerifiedCount = events.filter(
    (event) => event.meta?.stop_reason === "accepted_gate_verified"
  ).length;
  const last = events.length > 0 ? events[events.length - 1] : null;
  const lastAdapter = last?.meta?.adapter ?? "";
  const anyFullAdapter = events.some((event) => {
    const adapter = event.meta?.adapter;
    return typeof adapter === "string" && adapter.endsWith(":full");
  });
  const terminalFull = anyFullAdapter || (typeof lastAdapter === "string" && lastAdapter.endsWith(":full"));
  return {
    retrieval_hit_rate: attempts.length > 0 ? hits.length / attempts.length : 0,
    retrieval_attempts: attempts.length,
    retrieval_hits: hits.length,
    accepted_gate_retrieval_count: acceptedGateRetrievalCount,
    accepted_gate_verified_count: acceptedGateVerifiedCount,
    terminal_full: terminalFull,
    terminal_full_rate: terminalFull ? 1 : 0
  };
}

function formatRateWithCount(rate: number, hits: number, attempts: number): string {
  return `${(rate * 100).toFixed(1)}% (${hits}/${attempts})`;
}

function formatSignedPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}pp`;
}

function formatSignedNumber(next: number | null, base: number | null): string {
  if (typeof next !== "number" || typeof base !== "number") {
    return "-";
  }
  const delta = next - base;
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta}`;
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
