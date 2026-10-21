/** Windows that a list page opens itself (`/clients?open=<id>`): the address with the window and
 * the same address without it. Other filters in the address stay as they are. */
type Query = Record<string, string | string[] | undefined>;

export function withOpen(path: string, query: Query, id: string | null): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (key === "open" || value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, item);
  }
  if (id) params.set("open", id);
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

/** The id in `?open=`, when it looks like an id (the window renders only for those). */
export function openedId(query: Query): string | null {
  const value = Array.isArray(query.open) ? query.open[0] : query.open;
  return value && /^[0-9a-f-]{36}$/i.test(value) ? value : null;
}
