/** Wraps user-entered text (a business or client name) placed inside a translated sentence in
 * Unicode isolates, so a Hebrew name in an English sentence (or the reverse) keeps its own
 * direction and doesn't scramble the punctuation around it. */
export function isolate(text: string | null | undefined): string {
  return `⁨${text ?? ""}⁩`;
}

/** The `dir` for an input by its type: addresses and secrets are always left to right; free text
 * follows what the person types. */
export function inputDir(type: string | undefined): "ltr" | "auto" {
  switch (type) {
    case "email":
    case "tel":
    case "url":
    case "password":
    case "number":
      return "ltr";
    default:
      return "auto";
  }
}
