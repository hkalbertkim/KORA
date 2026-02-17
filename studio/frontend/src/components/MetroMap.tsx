type Props = {
  stations: string[];
  activeIndex: number;
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
};

export default function MetroMap({ stations, activeIndex, stationMetrics }: Props) {
  const startX = 40;
  const stepX = 120;
  const y = 70;
  const dotX = startX + Math.max(0, Math.min(activeIndex, stations.length - 1)) * stepX;

  return (
    <svg viewBox={`0 0 ${startX * 2 + stepX * (stations.length - 1)} 140`} className="metro-map">
      <line
        x1={startX}
        y1={y}
        x2={startX + stepX * (stations.length - 1)}
        y2={y}
        className="metro-line"
      />
      {stations.map((name, idx) => {
        const x = startX + idx * stepX;
        const active = idx <= activeIndex;
        const metric = stationMetrics[name];
        return (
          <g key={name}>
            <circle cx={x} cy={y} r={12} className={active ? "station active" : "station"} />
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
          </g>
        );
      })}
      <circle cx={dotX} cy={y} r={6} className="train-dot" />
    </svg>
  );
}
