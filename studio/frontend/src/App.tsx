import { useEffect, useMemo, useRef, useState } from "react";
import MetroMap from "./components/MetroMap";
import MetricsPanel from "./components/MetricsPanel";

type DemoReport = {
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

const STATIONS = ["Input", "Deterministic", "Decision", "Adapter", "Verify", "Output"];

export default function App() {
  const [prompt, setPrompt] = useState("Summarize this request path.");
  const [report, setReport] = useState<DemoReport>({});
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    fetch("/api/demo_report")
      .then((res) => res.json())
      .then((data) => setReport(data))
      .catch(() => setReport({}));
  }, []);

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

    const es = new EventSource("/api/sse_trace");
    eventSourceRef.current = es;

    es.addEventListener("station", (ev) => {
      try {
        const parsed = JSON.parse((ev as MessageEvent<string>).data) as TraceEvent;
        setTrace((prev) => [...prev, parsed]);
        const next = stationIndexMap[parsed.station];
        if (typeof next === "number") {
          setActiveIndex(next);
        }
      } catch {
        // Ignore malformed payloads in demo mode.
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
        <MetroMap stations={STATIONS} activeIndex={activeIndex} />
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
