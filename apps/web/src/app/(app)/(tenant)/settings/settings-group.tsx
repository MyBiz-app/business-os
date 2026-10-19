import type { ReactNode } from "react";

/** One group of a settings topic: a quiet heading and a line of help above a single card.
 * Always open and always in the same place, so nothing folds or jumps when the page loads. */
export function SettingsGroup({ id, title, description, children }: { id?: string; title: ReactNode; description?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className="flex scroll-anchor flex-col gap-3">
      <header className="flex max-w-[44rem] flex-col gap-0.5 px-1">
        <h3 id={id ? `${id}-title` : undefined} className="text-lg font-semibold tracking-tight">
          {title}
        </h3>
        {description && <p className="text-sm text-muted text-pretty">{description}</p>}
      </header>
      <div className="card p-5 sm:p-7">{children}</div>
    </section>
  );
}
