import type { ReactNode } from "react";

import { Container, type ContainerSize } from "./container";

/** The background of a full-width band. `inverse` is always dark (hero, AI band, call to action). */
export type SectionTone = "default" | "muted" | "surface" | "inverse";

const TONES: Record<SectionTone, string> = {
  default: "",
  muted: "bg-foreground/[0.03]",
  surface: "bg-surface",
  inverse: "section-inverse bg-navy text-white",
};

type SectionProps = {
  tone?: SectionTone;
  size?: ContainerSize;
  /** Vertical rhythm of the band. */
  spacing?: "compact" | "default" | "loose";
  id?: string;
  "aria-labelledby"?: string;
  className?: string;
  /** Classes for the inner container (for example a grid). */
  innerClassName?: string;
  children: ReactNode;
};

const SPACING = { compact: "section-y-compact", default: "section-y", loose: "section-y-loose" } as const;

/** A full-width band (its background reaches the screen's edges) holding a width-capped container. */
export function Section({
  tone = "default",
  size = "wide",
  spacing = "default",
  className = "",
  innerClassName = "",
  children,
  ...rest
}: SectionProps) {
  return (
    <section className={`w-full ${TONES[tone]} ${SPACING[spacing]} ${className}`.trim()} {...rest}>
      <Container size={size} className={innerClassName}>
        {children}
      </Container>
    </section>
  );
}
