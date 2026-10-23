/**
 * Catalog v2: what a business is built from, in three layers (spec: categories and service
 * model, section 2).
 *
 *   business type (tennis club, barbershop)   what the owner picks: words, services, questions
 *     -> activities (court rental, private lesson)
 *       -> service model (one of eight)        what the engine runs: calendar, availability, payment
 *
 * It sits next to the v1 catalog (index.ts) and changes nothing there: no screen, table or
 * migration reads it yet. Later slices fill the business from it (C2) and use it in sign-up (C7).
 * Source files: catalog-v2/*.json. `pnpm verticals:export` writes the checked-in copies.
 */
import { CATALOG_V2 } from "./catalog-v2.generated";

/** The eight service models. `support` says whether the booking engine already runs it. */
export const SERVICE_MODELS = {
  appointment: { code: "M1", support: "existing" },
  group_class: { code: "M2", support: "existing" },
  large_group: { code: "M3", support: "partial" },
  resource_rental: { code: "M4", support: "existing" },
  resource_staff: { code: "M5", support: "new" },
  open_entry: { code: "M6", support: "partial" },
  on_site: { code: "M7", support: "existing" },
  project: { code: "M8", support: "existing" },
} as const;
export type ServiceModel = keyof typeof SERVICE_MODELS;
export const SERVICE_MODEL_KEYS = Object.keys(SERVICE_MODELS) as ServiceModel[];

export const CALENDAR_VIEWS_V2 = ["staff_columns", "class_blocks", "resource_grid", "job_route"] as const;
export const DEPENDENTS_V2 = ["child", "pet", "vehicle"] as const;
export const DEPENDENTS_MODES = ["required", "optional", "ask"] as const;
export const QUESTION_KINDS = ["boolean", "number", "select", "multi_select", "text"] as const;
/** What one unit of a rental is; hours unless an activity says otherwise. */
export const BILLING_UNITS = ["hour", "half_day", "night"] as const;
/** The words for clients a business type can use (translations arrive with the terms slice). */
export const CUSTOMER_TERMS = [
  "member", "player", "client", "patient", "student", "customer", "owner", "guest",
  "trainee", "participant", "subscriber", "swimmer", "band",
] as const;

type Locales = Record<"he" | "en", string>;

export type DomainV2 = {
  key: string;
  order: number;
  icon: string;
  color: string;
  names: Locales;
  /** The v1 categories this domain replaces. */
  replaces: string[];
};

export type ResourceAttribute = {
  key: string;
  kind: "select" | "boolean" | "number";
  options?: string[];
};

export type ResourceTypeV2 = {
  key: string;
  names: Locales;
  default_capacity: number;
  default_minutes: number;
  min_minutes: number;
  max_minutes: number;
  step_minutes: number;
  attributes: ResourceAttribute[];
};

export type ActivityV2 = {
  key: string;
  names: Locales;
  model: ServiceModel;
  /** The shortest length of a rental; the length of anything else. */
  duration_minutes: number;
  /** Starting price in agorot (ILS minor units); 0 only for something marked coming_soon. */
  price_ils: number;
  capacity?: number;
  resource_type?: string;
  /** A rental's longest length and the step between lengths, in minutes. */
  max_minutes?: number;
  step_minutes?: number;
  unit?: (typeof BILLING_UNITS)[number];
  /** Large groups: the fewest staff members running one group. */
  min_staff?: number;
  travel_minutes?: number;
  /** Booked as a series (a weekly slot for a season, a course) rather than one time. */
  series?: boolean;
  online?: boolean;
  deposit?: boolean;
  /** Offered in sign-up but off until the owner turns it on. */
  optional?: boolean;
  coming_soon?: boolean;
};

export type ResourceSeed = { type: string; count: number; attributes?: Record<string, string | boolean | number> };

export type QuestionV2 = {
  key: string;
  text: Locales;
  kind: (typeof QUESTION_KINDS)[number];
  /** What the answer changes: `none`, `staff_count`, `dependents`, `time_billing`, `service_area`,
   * `axis:<name>` (the custom path), `activity:<key>`, `resource_count:<type>` or
   * `resource_attr:<type>.<attribute>` (`*` stands for all). */
  affects: string;
  options?: string[];
  default?: boolean | number | string | string[];
};

export type BusinessTypeV2 = {
  key: string;
  order: number;
  /** null only for the custom path. */
  domain: string | null;
  /** Other domains the type is listed under as well. */
  also_in?: string[];
  status: "live" | "beta" | "planned";
  names: Locales;
  synonyms: { he: string[]; en: string[] };
  /** The v1 set of industry words (`terms.<set>`). */
  terms: string;
  customer_term: (typeof CUSTOMER_TERMS)[number];
  customers: Locales;
  calendar_view: (typeof CALENDAR_VIEWS_V2)[number];
  activities: ActivityV2[];
  resources: ResourceSeed[];
  questions: QuestionV2[];
  /** Business types owners of this one often add (shown as "many also add"). */
  common_combos: string[];
  /** v1 keys that this type takes over (a business on one of them is mapped to it, slice C13). */
  replaces?: string[];
  dependents?: (typeof DEPENDENTS_V2)[number];
  dependents_mode?: (typeof DEPENDENTS_MODES)[number];
  time_billing?: boolean;
  custom?: boolean;
};

export type CatalogV2 = {
  version: 2;
  domains: DomainV2[];
  resource_types: ResourceTypeV2[];
  business_types: BusinessTypeV2[];
};

export { CATALOG_V2 };

const DOMAINS = new Map(CATALOG_V2.domains.map((d) => [d.key, d]));
const RESOURCE_TYPES = new Map(CATALOG_V2.resource_types.map((r) => [r.key, r]));
const TYPES = new Map(CATALOG_V2.business_types.map((t) => [t.key, t]));

export const domainsV2 = (): DomainV2[] => CATALOG_V2.domains;
export const domainV2 = (key: string | null | undefined) => (key ? DOMAINS.get(key) : undefined);
export const resourceTypes = (): ResourceTypeV2[] => CATALOG_V2.resource_types;
export const resourceType = (key: string | null | undefined) => (key ? RESOURCE_TYPES.get(key) : undefined);
export const businessTypes = (): BusinessTypeV2[] => CATALOG_V2.business_types;
export const businessType = (key: string | null | undefined) => (key ? TYPES.get(key) : undefined);

/** The business types listed under a domain (its own and the ones listed there as well). */
export function typesInDomain(domain: string): BusinessTypeV2[] {
  return CATALOG_V2.business_types.filter((t) => t.domain === domain || t.also_in?.includes(domain));
}

/** A business type open for sign-up (live or beta). */
export const isOpenV2 = (key: string | null | undefined): boolean => {
  const found = businessType(key);
  return found !== undefined && found.status !== "planned";
};

/** The activities a new business of this type starts with: everything not marked optional. */
export function defaultActivities(key: string): ActivityV2[] {
  return (businessType(key)?.activities ?? []).filter((a) => !a.optional && !a.coming_soon);
}

/** The business types that take over a v1 key (a category or sub-category), or the v1 key's
 * own successor when it keeps its name. */
export function successorsOf(legacyKey: string): BusinessTypeV2[] {
  const taken = CATALOG_V2.business_types.filter((t) => t.replaces?.includes(legacyKey));
  if (taken.length > 0) return taken;
  const same = businessType(legacyKey);
  return same ? [same] : [];
}

// --- Search -------------------------------------------------------------------------------

const FINAL_LETTERS: Record<string, string> = { ך: "כ", ם: "מ", ן: "נ", ף: "פ", ץ: "צ" };

/** Lower-case, no vowel points or quote marks, final letters as plain ones, single spaces. */
export function normalizeSearch(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFKC")
    .replace(/\u05BE/g, " ")
    .replace(/[\u0591-\u05BD\u05BF\u05C1-\u05C7]/g, "")
    .replace(/[ךםןףץ]/g, (c) => FINAL_LETTERS[c]!)
    .replace(/["'`´׳״’‘“”.,;:!?()/\\|_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function editDistanceAtMost(a: string, b: string, limit: number): boolean {
  if (Math.abs(a.length - b.length) > limit) return false;
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) {
      row[j] = Math.min(previous[j]! + 1, row[j - 1]! + 1, previous[j - 1]! + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    previous = row;
  }
  return previous[b.length]! <= limit;
}

const HEBREW_PREFIXES = /^[הבלוכמש](?=\S{3})/;

/** How well one query token matches one phrase token: 2 = same or a prefix of it, 1 = a typo away. */
function tokenMatch(query: string, token: string): number {
  const forms = HEBREW_PREFIXES.test(query) ? [query, query.slice(1)] : [query];
  for (const form of forms) if (token.startsWith(form)) return 2;
  for (const form of forms) {
    const limit = form.length >= 7 ? 2 : form.length >= 4 ? 1 : 0;
    if (limit > 0 && editDistanceAtMost(form, token, limit)) return 1;
  }
  return 0;
}

/** Scores a normalized query against one normalized phrase, 0 for no match. */
function scorePhrase(query: string, phrase: string): number {
  if (phrase === query) return 100;
  if (phrase.startsWith(query) && query.length >= 2) return 85;
  const queryTokens = query.split(" ");
  const phraseTokens = phrase.split(" ");
  const matches = queryTokens.map((q) => Math.max(...phraseTokens.map((p) => tokenMatch(q, p))));
  if (matches.every((m) => m === 2)) return 75;
  if (phrase.length >= 3 && query.includes(phrase)) return 70;
  if (query.length >= 3 && phrase.includes(query)) return 60;
  if (matches.every((m) => m >= 1)) return 45;
  return 0;
}

export type SearchHit = { key: string; score: number };

/**
 * Finds business types from what an owner types, in Hebrew or English: names, synonyms,
 * words inside a longer sentence ("tennis court in Ashdod"), a Hebrew prefix letter and one-letter
 * typos. Best match first; ties keep catalog order. Nothing is returned for text that matches nothing.
 */
export function searchBusinessTypes(text: string, limit = 8): SearchHit[] {
  const query = normalizeSearch(text);
  if (query.length < 2) return [];
  const hits: SearchHit[] = [];
  for (const type of CATALOG_V2.business_types) {
    const phrases = [type.names.he, type.names.en, ...type.synonyms.he, ...type.synonyms.en].map(normalizeSearch);
    const score = Math.max(...phrases.map((phrase) => scorePhrase(query, phrase)));
    if (score > 0) hits.push({ key: type.key, score });
  }
  return hits
    .sort((a, b) => b.score - a.score || TYPES.get(a.key)!.order - TYPES.get(b.key)!.order)
    .slice(0, limit);
}
