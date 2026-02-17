type Props = {
  stations: string[];
  activeIndex: number;
};

export default function MetroMap({ stations, activeIndex }: Props) {
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
        return (
          <g key={name}>
            <circle cx={x} cy={y} r={12} className={active ? "station active" : "station"} />
            <text x={x} y={110} textAnchor="middle" className="station-label">
              {name}
            </text>
          </g>
        );
      })}
      <circle cx={dotX} cy={y} r={6} className="train-dot" />
    </svg>
  );
}
