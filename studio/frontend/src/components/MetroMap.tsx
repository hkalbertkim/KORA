type Props = {
  stations: string[];
  activeIndex: number;
  runSkippedLLM: boolean;
  stationMetrics: Record<
    string,
    {
      status?: string;
      time_ms?: number;
      skipped?: boolean;
      tokens_in?: number;
      tokens_out?: number;
    }
  >;
  stationMetaSummary?: Record<
    string,
    {
      stop_reason?: string;
      retrieval_hit?: boolean;
      verifier_ok?: boolean;
    }
  >;
};

export default function MetroMap({
  stations,
  activeIndex,
  runSkippedLLM,
  stationMetrics,
  stationMetaSummary = {}
}: Props) {
  const startX = 40;
  const stepX = 120;
  const y = 70;
  const decisionIndex = stations.indexOf("Decision");
  const outputIndex = stations.indexOf("Output");
  const adapterIndex = stations.indexOf("Adapter");
  let dotX = startX + Math.max(0, Math.min(activeIndex, stations.length - 1)) * stepX;
  let dotY = y;
  if (runSkippedLLM && decisionIndex >= 0 && outputIndex > decisionIndex && activeIndex >= decisionIndex) {
    const progress = Math.max(0, Math.min(1, (activeIndex - decisionIndex) / (outputIndex - decisionIndex)));
    const decisionX = startX + decisionIndex * stepX;
    const outputX = startX + outputIndex * stepX;
    dotX = decisionX + (outputX - decisionX) * progress;
    dotY = y - 20;
  }

  return (
    <svg viewBox={`0 0 ${startX * 2 + stepX * (stations.length - 1)} 140`} className="metro-map">
      <line
        x1={startX}
        y1={y}
        x2={startX + stepX * Math.max(0, decisionIndex)}
        y2={y}
        className="metro-line active-path"
      />
      <line
        x1={startX + stepX * Math.max(0, decisionIndex)}
        y1={y}
        x2={startX + stepX * (stations.length - 1)}
        y2={y}
        className={runSkippedLLM ? "metro-line inactive-path" : "metro-line active-path"}
      />
      {decisionIndex >= 0 && outputIndex > decisionIndex && (
        <line
          x1={startX + decisionIndex * stepX}
          y1={y}
          x2={startX + outputIndex * stepX}
          y2={y - 20}
          className={runSkippedLLM ? "metro-line active-path bypass-line" : "metro-line inactive-path bypass-line"}
        />
      )}
      {runSkippedLLM && decisionIndex >= 0 && (
        <g>
          <rect
            x={startX + decisionIndex * stepX - 18}
            y={y - 50}
            width={36}
            height={16}
            rx={6}
            className="skip-badge"
          />
          <text x={startX + decisionIndex * stepX} y={y - 39} textAnchor="middle" className="skip-badge-text">
            SKIP
          </text>
        </g>
      )}
      {stations.map((name, idx) => {
        const x = startX + idx * stepX;
        const active = idx <= activeIndex;
        const metric = stationMetrics[name];
        const meta = stationMetaSummary[name];
        const dimmedAdapter = runSkippedLLM && idx === adapterIndex;
        const badges: string[] = [];
        if (meta?.retrieval_hit) {
          badges.push("R-HIT");
        } else if ((meta?.stop_reason ?? "").includes("accepted_gate_verified")) {
          badges.push("G-OK");
        } else if (meta?.stop_reason) {
          badges.push(`SR:${shortStopReason(meta.stop_reason)}`);
        }
        if (meta?.verifier_ok) {
          badges.push("V");
        }
        return (
          <g key={name}>
            <circle
              cx={x}
              cy={y}
              r={12}
              className={dimmedAdapter ? "station dim" : active ? "station active" : "station"}
            />
            <text x={x} y={110} textAnchor="middle" className="station-label">
              {name}
            </text>
            {metric && (
              <g className="station-metric">
                <rect x={x - 45} y={10} width={90} height={28} rx={6} className="metric-badge" />
                <text x={x} y={22} textAnchor="middle" className="metric-text">
                  {String(metric.status ?? "-")} · {String(metric.time_ms ?? 0)}ms
                </text>
                {name === "Adapter" && (metric.tokens_in !== undefined || metric.tokens_out !== undefined) && (
                  <text x={x} y={33} textAnchor="middle" className="metric-text small">
                    in:{String(metric.tokens_in ?? 0)} out:{String(metric.tokens_out ?? 0)}
                  </text>
                )}
              </g>
            )}
            {badges.length > 0 && (
              <g className="station-metric">
                <rect x={x - 45} y={42} width={90} height={14} rx={6} className="metric-badge" />
                <text x={x} y={52} textAnchor="middle" className="metric-text small">
                  {badges.join(" ")}
                </text>
              </g>
            )}
          </g>
        );
      })}
      <circle cx={dotX} cy={dotY} r={6} className="train-dot" />
    </svg>
  );
}

function shortStopReason(reason: string): string {
  const normalized = reason.trim();
  if (normalized.length <= 14) {
    return normalized;
  }
  return `${normalized.slice(0, 14)}...`;
}
