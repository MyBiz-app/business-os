const COLORS = ["#2563EB", "#7C3AED", "#06B6D4", "#F59E0B", "#10B981", "#EC4899"];
const WIDTH = 640;
const HEIGHT = 200;
const PAD = { left: 52, right: 8, top: 8, bottom: 22 };

type Series = { key: string; label: string; points: { day: string; value: number }[] };

/** Several lines on one shared scale (followers per network). Rendered on the server: each line
 * is described for screen readers and the same numbers are offered as a table. */
export function LineChart({
  title,
  series,
  formatTick,
  formatDay,
  tableLabel,
  dayHeader,
}: {
  title: string;
  series: Series[];
  formatTick: (value: number) => string;
  formatDay: (day: string) => string;
  tableLabel: string;
  dayHeader: string;
}) {
  const days = [...new Set(series.flatMap((s) => s.points.map((p) => p.day)))].sort();
  const values = series.flatMap((s) => s.points.map((p) => p.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const low = min - span * 0.05;
  const high = max + span * 0.05;
  const x = (day: string) => PAD.left + (days.indexOf(day) / Math.max(days.length - 1, 1)) * (WIDTH - PAD.left - PAD.right);
  const y = (value: number) => PAD.top + (1 - (value - low) / (high - low)) * (HEIGHT - PAD.top - PAD.bottom);
  const ticks = [low + (high - low) * 0.05, (low + high) / 2, high - (high - low) * 0.05];
  const first = days[0];
  const last = days[days.length - 1];
  return (
    <figure className="flex min-w-0 flex-col gap-3">
      <figcaption className="font-semibold">{title}</figcaption>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {series.map((s, index) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-0.5 w-4 rounded-full" style={{ background: COLORS[index % COLORS.length] }} />
            {s.label}
          </li>
        ))}
      </ul>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={title} className="w-full" style={{ direction: "ltr" }}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(tick)} y2={y(tick)} className="stroke-border" strokeDasharray="3 4" />
            <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="fill-muted text-[11px]">
              {formatTick(tick)}
            </text>
          </g>
        ))}
        {series.map((s, index) => (
          <polyline
            key={s.key}
            fill="none"
            stroke={COLORS[index % COLORS.length]}
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={s.points.map((p) => `${x(p.day)},${y(p.value)}`).join(" ")}
          />
        ))}
        <text x={PAD.left} y={HEIGHT - 4} className="fill-muted text-[11px]">
          {formatDay(first)}
        </text>
        <text x={WIDTH - PAD.right} y={HEIGHT - 4} textAnchor="end" className="fill-muted text-[11px]">
          {formatDay(last)}
        </text>
      </svg>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-primary-ink">{tableLabel}</summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className="w-full text-start">
            <thead>
              <tr>
                <th scope="col" className="p-1.5 text-start">{dayHeader}</th>
                {series.map((s) => (
                  <th key={s.key} scope="col" className="p-1.5 text-start">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {days.map((day) => (
                <tr key={day} className="border-t border-border">
                  <th scope="row" className="p-1.5 text-start font-normal">{formatDay(day)}</th>
                  {series.map((s) => (
                    <td key={s.key} className="p-1.5">
                      {formatTick(s.points.find((p) => p.day === day)?.value ?? 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
