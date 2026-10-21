/** The query parameter that lists the hidden columns, so a view (a bookmark, a saved view) keeps them.
 * Lives apart from the client component so server pages can read it (a "use client" module's exports
 * are references on the server, not values). */
export const HIDDEN_COLUMNS_PARAM = "hide";

export function hiddenColumns(value: string | string[] | undefined, allowed: string[]) {
  const raw = Array.isArray(value) ? value.join(",") : (value ?? "");
  return raw.split(",").filter((key) => allowed.includes(key));
}
