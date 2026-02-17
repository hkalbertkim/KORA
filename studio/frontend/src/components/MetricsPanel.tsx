type Props = {
  report: Record<string, unknown>;
};

export default function MetricsPanel({ report }: Props) {
  const stageCounts = (report.stage_counts as Record<string, number> | undefined) ?? {};

  return (
    <div>
      <h2>Metrics</h2>
      <div className="metrics-grid">
        <Metric label="LLM Calls" value={report.total_llm_calls} />
        <Metric label="Tokens In" value={report.tokens_in} />
        <Metric label="Tokens Out" value={report.tokens_out} />
        <Metric label="Estimated Cost (USD)" value={report.estimated_cost_usd} />
      </div>
      <h3>Stage Counts</h3>
      <pre>{JSON.stringify(stageCounts, null, 2)}</pre>
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
