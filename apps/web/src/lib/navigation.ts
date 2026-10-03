/** Returns `next` only if it is a same-site path, never an absolute or protocol-relative URL. */
export function safeNext(next: unknown): string | null {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

export const AUTH_NEXT_COOKIE = "AUTH_NEXT";
