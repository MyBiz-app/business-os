type Cell = { weekday: number; hour: number; value: number };

/** Average engagement per post by weekday and hour: the darker the cell, the better the slot. */
export function Heatmap({
  cells,
  weekdays,
  title,
  hint,
  best,
}: {
  cells: Cell[];
  /** Day names, Sunday first. */
  weekdays: string[];
  title: string;
  hint: string;
  best: string | null;
}) {
  const max = Math.max(...cells.map((c) => c.value), 1);
  const hours = Array.from({ length: 24 }, (_, hour) => hour);
  const byKey = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c.value]));
  return (
    <figure className="flex min-w-0 flex-col gap-3">
      <figcaption className="font-semibold">{title}</figcaption>
      <p className="text-sm text-muted">{hint}</p>
      {best && <p className="text-sm font-semibold text-primary-ink">{best}</p>}
      <div className="overflow-x-auto" dir="ltr" role="group" aria-label={title} tabIndex={0}>
        <table className="min-w-[36rem] border-separate border-spacing-0.5 text-[11px]">
          <thead>
            <tr>
              <td />
              {hours.map((hour) => (
                <th key={hour} scope="col" className="w-5 text-center font-normal text-muted">
                  <span className={hour % 3 === 0 ? undefined : "sr-only"}>{hour}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weekdays.map((name, weekday) => (
              <tr key={name}>
                <th scope="row" className="pe-2 text-start font-normal text-muted">
                  {name}
                </th>
                {hours.map((hour) => {
                  const value = byKey.get(`${weekday}-${hour}`);
                  return (
                    <td
                      key={hour}
                      title={value === undefined ? undefined : `${name} ${hour}:00 · ${value}`}
                      className="h-5 rounded-sm bg-foreground/5"
                      style={value === undefined ? undefined : { background: `color-mix(in srgb, var(--color-primary) ${Math.round(15 + (value / max) * 85)}%, transparent)` }}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
