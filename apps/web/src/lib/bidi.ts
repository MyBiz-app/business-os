/** Wraps user-entered text (a business or client name) placed inside a translated sentence in
 * Unicode isolates, so a Hebrew name in an English sentence (or the reverse) keeps its own
 * direction and doesn't scramble the punctuation around it. */
export function isolate(text: string | null | undefined): string {
  return `⁨${text ?? ""}⁩`;
}
