type Props = {
  report: Record<string, unknown>;
  retrievalSummary?: {
    retrieval_hit_rate: number;
    retrieval_attempts: number;
    retrieval_hits: number;
    accepted_gate_retrieval_count: number;
    accepted_gate_verified_count: number;
    terminal_full: boolean;
    terminal_full_rate: number;
  };
  recentStationEvents?: Array<{
    station: string;
    stage: string;
    status: string;
    time_ms: number;
    tokens_in?: number;
    tokens_out?: number;
    meta?: {
      stop_reason?: string;
      gate_retrieval_hit?: boolean;
      gate_retrieval_strategy?: string;
    };
  }>;
};

export default function MetricsPanel({ report, retrievalSummary, recentStationEvents }: Props) {
  const stageCounts = (report.stage_counts as Record<string, number> | undefined) ?? {};
  const summary = retrievalSummary ?? {
    retrieval_hit_rate: 0,
    retrieval_attempts: 0,
    retrieval_hits: 0,
    accepted_gate_retrieval_count: 0,
    accepted_gate_verified_count: 0,
    terminal_full: false,
    terminal_full_rate: 0
  };
  const events = recentStationEvents ?? [];

  return (
    <div>
      <h2>Metrics</h2>
      <div className="metrics-grid">
        <Metric label="Run OK" value={report.ok} />
        <Metric label="Total Time (ms)" value={report.total_time_ms} />
        <Metric label="LLM Calls" value={report.total_llm_calls} />
        <Metric label="Tokens In" value={report.tokens_in} />
        <Metric label="Tokens Out" value={report.tokens_out} />
        <Metric label="Estimated Cost (USD)" value={report.estimated_cost_usd} />
        <Metric
          label="Retrieval Hit Rate"
          value={`${(summary.retrieval_hit_rate * 100).toFixed(1)}% (${summary.retrieval_hits}/${summary.retrieval_attempts})`}
        />
        <Metric label="Accepted Gate Retrieval" value={summary.accepted_gate_retrieval_count} />
        <Metric label="Accepted Gate Verified" value={summary.accepted_gate_verified_count} />
        <Metric label="Terminal Full" value={summary.terminal_full ? "yes" : "no"} />
        <Metric label="Terminal Full Rate" value={`${(summary.terminal_full_rate * 100).toFixed(0)}%`} />
      </div>
      <h3>Stage Counts</h3>
      <pre>{JSON.stringify(stageCounts, null, 2)}</pre>
      <h3>Recent Stations</h3>
      <table>
        <thead>
          <tr>
            <th>station</th>
            <th>status</th>
            <th>time_ms</th>
            <th>tokens_in</th>
            <th>tokens_out</th>
            <th>stop_reason</th>
            <th>gate_retrieval_hit</th>
            <th>gate_retrieval_strategy</th>
          </tr>
        </thead>
        <tbody>
          {events.slice(-20).map((event, idx) => (
            <tr key={`${event.stage}-${idx}`}>
              <td>{event.station}</td>
              <td>{event.status}</td>
              <td>{event.time_ms}</td>
              <td>{event.tokens_in ?? "-"}</td>
              <td>{event.tokens_out ?? "-"}</td>
              <td>{event.meta?.stop_reason ?? "-"}</td>
              <td>
                {typeof event.meta?.gate_retrieval_hit === "boolean"
                  ? String(event.meta.gate_retrieval_hit)
                  : "-"}
              </td>
              <td>{event.meta?.gate_retrieval_strategy ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{String(value ?? "-")}</div>
    </div>
  );
}
