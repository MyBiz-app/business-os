/** Where the page should be after the address moved to another page. Kept apart from the
 * component so the rules can be tested without a browser. */
export type ScrollPlan = { kind: "keep" } | { kind: "top" } | { kind: "restore"; y: number } | { kind: "anchor"; id: string };

export function planNavigation(input: {
  pathname: string;
  previous: string;
  /** The address has a `#id`. */
  hash: string;
  /** The move came from the browser's back or forward button. */
  traversal: boolean;
  /** Where the person was the last time they were on `pathname`. */
  saved: number | undefined;
  /** A window (an intercepted route) is open over the page. */
  windowOpen: boolean;
  /** The page beneath an open window, while there is one. */
  under: string | null;
}): { plan: ScrollPlan; under: string | null } {
  // A window opens over the page, or closes back to it: the page stays where it is.
  if (input.windowOpen) return { plan: { kind: "keep" }, under: input.under ?? input.previous };
  if (input.under !== null && input.pathname === input.under) return { plan: { kind: "keep" }, under: null };
  if (input.traversal && input.saved !== undefined) return { plan: { kind: "restore", y: input.saved }, under: null };
  let id = input.hash.replace(/^#/, "");
  try {
    id = decodeURIComponent(id);
  } catch {
    // A malformed escape: use the text as it is.
  }
  if (id) return { plan: { kind: "anchor", id }, under: null };
  return { plan: { kind: "top" }, under: null };
}
