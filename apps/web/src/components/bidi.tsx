import type { ElementType, ReactNode } from "react";

export { inputDir } from "@/lib/bidi";

/** A value that is always written left to right inside a sentence of either language: an email,
 * phone number, web address, code, order number or price. `bdi` isolates it from the words
 * around it (so the dot or comma next to it doesn't jump to the wrong side) and `dir="ltr"`
 * fixes its own order. */
export function Ltr({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <bdi dir="ltr" className={className}>
      {children}
    </bdi>
  );
}

/** Text a person typed (a client's name, a service, a note): its direction follows its first
 * letters, whatever language the page is in. Use `as="p"` / `as="div"` for a block. */
export function UserText({ children, as: Tag = "bdi", className }: { children: ReactNode; as?: ElementType; className?: string }) {
  return (
    <Tag dir="auto" className={className}>
      {children}
    </Tag>
  );
}

/** Rich-text helper for translations: `t.rich("intro", { brand: brandText })` keeps the product
 * name from reordering the punctuation next to it in a Hebrew sentence. */
export function brandText(chunks: ReactNode) {
  return <bdi dir="ltr">{chunks}</bdi>;
}

/** An icon that points somewhere (arrow, chevron, "next", "back"): mirrored in right-to-left.
 * Icons without a direction (sun, trash, phone) don't need it. */
export const DIRECTIONAL_ICON = "rtl:-scale-x-100";
