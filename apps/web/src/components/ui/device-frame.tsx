import type { CSSProperties, ReactNode } from "react";

type Props = {
  /** A phone (portrait) or a laptop (landscape with a base). */
  device: "phone" | "laptop";
  /** The screen content. Rendered inside the glass; it should fill the box. */
  children: ReactNode;
  className?: string;
  /** Laptop only: how far the lid is open, 0 (closed) to 1 (open). Drive it from a CSS variable for scroll scenes. */
  lid?: number | string;
};

/**
 * A CSS-drawn phone or laptop that holds live HTML as its screen. No images, no brand marks:
 * the shapes are generic rounded hardware. The frame is decorative (aria-hidden); put the real
 * content outside it or give the page the same facts as text.
 */
export function DeviceFrame({ device, children, className = "", lid = 1 }: Props) {
  if (device === "phone") {
    return (
      <div
        aria-hidden="true"
        className={`relative mx-auto aspect-[9/19] w-64 rounded-[2.75rem] border-[10px] border-foreground/85 bg-background shadow-2xl ${className}`}
      >
        <span className="absolute start-1/2 top-2 z-10 h-5 w-20 -translate-x-1/2 rounded-full bg-foreground/85 rtl:translate-x-1/2" />
        <div className="absolute inset-0 flex flex-col overflow-hidden rounded-[2.1rem] px-3 pb-5 pt-9">{children}</div>
        <span className="absolute inset-x-0 bottom-1.5 mx-auto h-1 w-20 rounded-full bg-foreground/25" />
      </div>
    );
  }
  return (
    <div aria-hidden="true" className={`mx-auto w-full max-w-3xl [perspective:1800px] ${className}`}>
      <div
        className="relative origin-bottom rounded-t-2xl border-[10px] border-b-0 border-foreground/85 bg-background shadow-2xl [transform-style:preserve-3d]"
        style={{ transform: "rotateX(calc((1 - var(--lid-open, 1)) * -88deg))", "--lid-open": lid } as CSSProperties}
      >
        <span className="absolute start-1/2 top-1 z-10 size-1.5 -translate-x-1/2 rounded-full bg-foreground/30 rtl:translate-x-1/2" />
        <div className="aspect-[16/10] overflow-hidden rounded-t-md p-3">{children}</div>
      </div>
      <div className="relative mx-[-3%] h-3 rounded-b-2xl bg-gradient-to-b from-foreground/25 to-foreground/10 shadow-xl">
        <span className="absolute inset-x-0 top-0 mx-auto h-1 w-1/5 rounded-b-md bg-foreground/20" />
      </div>
    </div>
  );
}
