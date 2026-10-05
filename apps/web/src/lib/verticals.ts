/** The industry catalog's texts and words, for the web app's translators. Texts live in
 * `verticals.<key>` and fall back to the parent category; words in `terms.<set>`; client-field
 * labels in `clientFields.<key>`. The casts name one real key so next-intl's typed keys accept
 * the dynamic ones, which packages/verticals' tests check exist for every entry. */
import { categories, childrenOf, termsOf, textKey } from "@business-os/verticals";

import type { Messages } from "@business-os/i18n";

type Values = Record<string, string | number | Date>;
type Text = "name" | "tagline" | "heroTitle" | "heroText" | "yours" | "example";
type Term = keyof Messages["terms"]["fitness"];

/** The root translator (`useTranslations()` / `getTranslations()`), as these helpers use it. */
type Translator = {
  (key: `verticals.fitness.${Text}` | `terms.fitness.${Term}` | "clientFields.notSet", values?: Values): string;
  has(key: `verticals.fitness.${Text | "points"}`): boolean;
  raw(key: "verticals.fitness.points"): unknown;
};

export function industryTexts(t: Translator) {
  const has = (path: string) => t.has(path as "verticals.fitness.name");
  return {
    /** One of an industry's texts, from it or its nearest parent. */
    text: (key: string, name: Text, values?: Values) => t(textKey(key, name, has) as `verticals.fitness.${Text}`, values),
    /** An industry's three benefits, from it or its nearest parent. */
    points: (key: string) => t.raw(textKey(key, "points", has) as "verticals.fitness.points") as string[],
    /** A word in the business's industry (clients, schedule, …). */
    term: (vertical: string, name: Term, values?: Values) =>
      t(`terms.${termsOf(vertical)}.${name}` as `terms.fitness.${Term}`, values),
  };
}

/**
 * The industries as select options, grouped by category: its kinds of business, then the
 * category itself labeled `otherKind(name)`. With `soon`, categories coming soon follow under
 * that group (for the contact form); otherwise only industries open for sign-up are listed.
 */
export function industryOptions(
  text: (key: string, name: "name") => string,
  otherKind: (name: string) => string,
  soon?: string,
): { value: string; label: string; group?: string }[] {
  return categories().flatMap((category) => {
    const name = text(category.key, "name");
    if (category.status === "planned") return soon ? [{ value: category.key, label: name, group: soon }] : [];
    const kinds = childrenOf(category.key).filter((kind) => kind.status !== "planned");
    if (kinds.length === 0) return [{ value: category.key, label: name, group: name }];
    return [
      ...kinds.map((kind) => ({ value: kind.key, label: text(kind.key, "name"), group: name })),
      { value: category.key, label: otherKind(name), group: name },
    ];
  });
}
