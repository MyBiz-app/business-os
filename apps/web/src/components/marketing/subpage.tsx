import type { ReactNode } from "react";

import { Container } from "@/components/layout/container";

type SubpageHeroProps = {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  /** Buttons or chips under the text. */
  children?: ReactNode;
  /** A picture or mock on the far side; without it the text sits alone, start-aligned. */
  aside?: ReactNode;
  /** Something above the eyebrow (an icon tile). */
  lead?: ReactNode;
};

/** The dark band that opens a marketing subpage, on the home hero's navy glow: text on one side and
 * an optional picture on the other (stacked on a phone). The band reaches the screen's edges; the
 * content is capped at the wide container. Always dark, so its text is explicitly light. */
export function SubpageHero({ eyebrow, title, description, children, aside, lead }: SubpageHeroProps) {
  return (
    <section className="section-inverse relative isolate w-full overflow-hidden bg-navy text-white section-y">
      <div aria-hidden="true" className="mk-grid pointer-events-none absolute inset-0 -z-10" />
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 start-[10%] -z-10 size-[30rem] rounded-full bg-primary/35 blur-[120px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-48 end-[8%] -z-10 size-[26rem] rounded-full bg-electric/20 blur-[120px]" />
      <Container className={aside ? "grid items-center gap-12 lg:grid-cols-2" : ""}>
        <div className="flex max-w-[44rem] flex-col items-start gap-5">
          {lead}
          {eyebrow && <p className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85">{eyebrow}</p>}
          <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-balance sm:text-5xl">{title}</h1>
          {description && <p className="text-lg leading-relaxed text-white/75 text-pretty sm:text-xl">{description}</p>}
          {children}
        </div>
        {aside}
      </Container>
    </section>
  );
}

/** Text for one side of a wide two-column band: eyebrow, heading, paragraph, optional extras. */
export function BandText({ eyebrow, title, text, id, children }: { eyebrow?: string; title: string; text?: string; id?: string; children?: ReactNode }) {
  return (
    <div className="flex max-w-[44rem] flex-col gap-4">
      {eyebrow && <p className="text-sm font-semibold uppercase tracking-wide text-primary-ink">{eyebrow}</p>}
      <h2 id={id} className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {text && <p className="text-lg text-muted text-pretty">{text}</p>}
      {children}
    </div>
  );
}
