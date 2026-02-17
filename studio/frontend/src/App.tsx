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
};

type SummaryEvent = {
  ok: boolean;
  total_llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  estimated_cost_usd?: number;
};

type StationMetric = {
  status?: string;
  time_ms?: number;
  skipped?: boolean;
  tokens_in?: number;
  tokens_out?: number;
};

const STATIONS = ["Input", "Deterministic", "Decision", "Adapter", "Verify", "Output"];

export default function App() {
  const [prompt, setPrompt] = useState("Summarize this request path.");
  const [report, setReport] = useState<DemoReport>({});
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [runSkippedLLM, setRunSkippedLLM] = useState(false);
  const [stationMetrics, setStationMetrics] = useState<Record<string, StationMetric>>({});
  const eventSourceRef = useRef<EventSource | null>(null);

  const stationIndexMap = useMemo(() => {
    const out: Record<string, number> = {};
    STATIONS.forEach((name, idx) => {
      out[name] = idx;
    });
    return out;
  }, []);

  const replay = async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setPlaying(true);
    setActiveIndex(0);
    setTrace([]);
    setRunSkippedLLM(false);
    setStationMetrics({});
    setReport({});
    try {
      const runRes = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, mode: "kora", adapter: "mock" })
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
        <button onClick={replay} disabled={playing}>
          {playing ? "Replaying..." : "Replay Demo Trace"}
        </button>
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
        <MetricsPanel report={report} />
      </section>
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
