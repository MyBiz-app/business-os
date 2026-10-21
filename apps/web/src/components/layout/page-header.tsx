import type { ReactNode } from "react";

type PageHeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  /** A small label above the title. */
  eyebrow?: ReactNode;
  /** Buttons on the far side of the title row; on a phone they fill a tidy grid under it. */
  actions?: ReactNode;
  /** Id for the heading, so a section can name itself with aria-labelledby. */
  titleId?: string;
  className?: string;
};

/** The same page heading on every screen: title, optional lead-in text, optional actions. */
export function PageHeader({ title, description, eyebrow, actions, titleId, className = "" }: PageHeaderProps) {
  return (
    <header className={`flex flex-wrap items-end justify-between gap-x-6 gap-y-4 ${className}`.trim()}>
      <div className="flex min-w-0 max-w-[44rem] flex-col gap-2">
        {eyebrow && <p className="text-sm font-semibold uppercase tracking-wide text-primary-ink">{eyebrow}</p>}
        <h1 id={titleId} className="text-2xl font-semibold text-balance">
          {title}
        </h1>
        {description && <p className="text-sm text-muted text-pretty sm:text-base">{description}</p>}
      </div>
      {actions && <div className="grid w-full grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] items-center gap-2 *:justify-center sm:flex sm:w-auto sm:flex-wrap">{actions}</div>}
    </header>
  );
}
