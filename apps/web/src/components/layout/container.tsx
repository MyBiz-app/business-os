import type { ElementType, ReactNode } from "react";

/** How wide a page's content may grow. All sizes keep fluid side gutters (`page-gutter`). */
export type ContainerSize = "wide" | "default" | "narrow" | "prose" | "full";

const SIZES: Record<ContainerSize, string> = {
  /** Up to 1440px: marketing pages and wide grids. */
  wide: "max-w-[90rem]",
  /** Up to 1200px: forms with side panels, settings. */
  default: "max-w-[75rem]",
  /** Up to 880px: a single column such as a wizard step. */
  narrow: "max-w-[55rem]",
  /** About 70 characters: long paragraphs. Place it inside a wide grid, not alone in the middle. */
  prose: "max-w-[44rem]",
  /** No cap: the CRM, whose tables and calendar use the whole screen. */
  full: "max-w-none",
};

type ContainerProps = {
  size?: ContainerSize;
  as?: ElementType;
  className?: string;
  children: ReactNode;
} & Omit<React.HTMLAttributes<HTMLElement>, "className" | "children">;

/** The page's one width rule: centered, capped at `size`, with gutters that grow with the screen. */
export function Container({ size = "wide", as: Tag = "div", className = "", children, ...rest }: ContainerProps) {
  return (
    <Tag id={Tag === "main" ? "main" : undefined} className={`mx-auto w-full page-gutter ${SIZES[size]} ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}
