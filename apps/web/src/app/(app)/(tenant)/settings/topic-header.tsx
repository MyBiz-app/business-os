import type { ReactNode } from "react";

/** The title of a settings topic. The room's page title is the one h1, so a topic is an h2. */
export function TopicHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="flex min-w-0 max-w-[44rem] flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight text-balance">{title}</h2>
        {description && <p className="text-muted text-pretty">{description}</p>}
      </div>
      {actions}
    </header>
  );
}
