/** Initials of a name ("נועה כהן" → "נכ", "dana levi" → "DL"), for avatars. */
export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

/** A person's full name from its parts, skipping what is missing. */
export function fullName(first: string | null | undefined, last?: string | null): string {
  return [first, last].filter((part) => part && part.trim()).join(" ");
}
