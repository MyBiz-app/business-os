import type { ReactNode } from "react";

export type RecordStat = { key: string; label: string; value: ReactNode };

type RecordHeaderProps = {
  avatar: ReactNode;
  name: string;
  /** In a window the title bar already says the name, so the page's one heading is not repeated. */
  inModal?: boolean;
  /** Status next to the name (a `Badge`). */
  badges?: ReactNode;
  /** One quiet line under the name (joined, branch, stage). */
  subtitle?: ReactNode;
  /** The main action first (`Button` / `ButtonLink`), then the quiet ones. */
  actions?: ReactNode;
  /** One thin line of numbers under the header. */
  stats?: RecordStat[];
};

/** The head of a Record page (a client, a lead): who it is, its status, what to do next, and one
 * line of numbers. Calm: no tinted panel, hierarchy by size and hairlines. */
export function RecordHeader({ avatar, name, inModal = false, badges, subtitle, actions, stats }: RecordHeaderProps) {
  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 items-center gap-4">
          {avatar}
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {inModal ? (
                <p dir="auto" className="truncate text-2xl font-semibold">
                  {name}
                </p>
              ) : (
                <h1 dir="auto" className="truncate text-2xl font-semibold">
                  {name}
                </h1>
              )}
              {badges}
            </div>
            {subtitle && <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {stats && stats.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:flex sm:flex-wrap sm:gap-x-0 sm:gap-y-2 sm:*:px-5 sm:*:first:ps-0 sm:*:not-first:border-s sm:*:border-border">
          {stats.map((stat) => (
            <div key={stat.key} className="flex min-w-0 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-2">
              <dt className="text-muted">{stat.label}</dt>
              <dd className="font-semibold tabular-nums">{stat.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </header>
  );
}
