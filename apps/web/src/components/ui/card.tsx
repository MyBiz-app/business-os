import type { ElementType, HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

type CardProps = HTMLAttributes<HTMLElement> & {
  /** The element: a `section` for a titled block, an `li` inside a list, `article` for a record. */
  as?: ElementType;
  /** md: 16px on a phone and 20px on a desktop. sm: tighter. none: the content brings its own (a table, a list with dividers). */
  padding?: "md" | "sm" | "none";
  /** accent: the one tinted surface of a view (a tip, a plan, a call to action). */
  tone?: "default" | "accent";
  /** The whole card reacts to the pointer (it is, or contains, the link). */
  interactive?: boolean;
};

const PADDING = { md: "p-4 sm:p-5", sm: "p-3 sm:p-4", none: "" } as const;

/** A flat surface with a hairline border (Calm: no shadow, no gradient). Never put a card inside a
 * card: group numbers with dividers instead. */
export function Card({ as: Tag = "div", padding = "md", tone = "default", interactive = false, className, ...props }: CardProps) {
  return <Tag {...props} className={cx(tone === "accent" ? "card-accent" : "card", interactive && "card-hover", PADDING[padding], className)} />;
}

/** The title row of a card: a 17px heading with an optional line under it and actions at the end. */
export function CardHeader({
  title,
  description,
  actions,
  titleId,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Id for the heading, so the card can name itself with aria-labelledby. */
  titleId?: string;
  className?: string;
}) {
  return (
    <div className={cx("mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-2", className)}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h2 id={titleId} className="text-lg font-semibold text-balance">
          {title}
        </h2>
        {description && <p className="text-sm text-muted text-pretty">{description}</p>}
      </div>
      {actions && <div className="flex max-w-full shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
