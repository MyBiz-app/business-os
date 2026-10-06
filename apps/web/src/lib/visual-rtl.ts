/** A right-to-left line in visual (left-to-right) order, for renderers without bidi support,
 * such as the share-image renderer: the characters are reversed, then runs of Latin letters
 * and digits ("AI", "14") are put back the right way round, and brackets are mirrored.
 * Meant for one short line at a time (a wrapped line would reorder wrongly). */
export function visualRtl(line: string): string {
  const mirrored: Record<string, string> = { "(": ")", ")": "(", "[": "]", "]": "[", "<": ">", ">": "<" };
  const reversed = [...line].reverse().map((char) => mirrored[char] ?? char).join("");
  return reversed.replace(/[A-Za-z0-9][A-Za-z0-9.,:%'\-]*[A-Za-z0-9]|[A-Za-z0-9]/g, (run) => [...run].reverse().join(""));
}
