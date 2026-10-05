/**
 * The industry catalog: categories and their sub-categories, shared by the API (through a
 * checked-in copy, see scripts/export-api.mjs), the website and the apps.
 *
 * A category sets the defaults for a family of businesses that work the same way; a
 * sub-category inherits everything from its parent and overrides only what it lists. The core
 * never branches on the industry: it reads the resolved entry.
 *
 * To add one: `pnpm vertical:new <key> [--parent <category>]`, then `pnpm verticals:export`
 * (see docs/verticals.md).
 */
import { CATALOG } from "./catalog.generated";

/** live: open for sign-up · beta: open, marked new · planned: shown as "coming soon". */
export const STATUSES = ["live", "beta", "planned"] as const;
export const ICONS = [
  "dumbbell", "scissors", "stethoscope", "graduation-cap", "car",
  "trophy", "wrench", "paw-print", "camera", "briefcase",
] as const;
export const FIELD_KINDS = ["text", "long_text", "number", "date", "select"] as const;
export const BOOKING_MODES = ["class", "appointment"] as const;
export const PRESETS = ["starter", "growing", "ai_powered"] as const;
export const RECOMMENDABLE = ["client_app", "ai", "crm", "whatsapp"] as const;
export const LOCALES = ["he", "en"] as const;
export const CURRENCIES = ["ILS", "USD", "EUR"] as const;

export type Status = (typeof STATUSES)[number];
export type Icon = (typeof ICONS)[number];

export type ClientField = {
  key: string;
  kind: (typeof FIELD_KINDS)[number];
  options?: string[];
  max_length?: number;
};

export type DefaultService = {
  names: Record<string, string>;
  duration_minutes: number;
  booking_mode: (typeof BOOKING_MODES)[number];
  prices: Record<string, number>;
  color: string;
  capacity?: number;
};

export type DefaultPlan = {
  names: Record<string, string>;
  kind: "membership" | "punch_card";
  validity_days: number;
  prices: Record<string, number>;
  credits?: number;
};

/** One catalog entry as written in catalog/*.json: everything but the key and status is
 * optional on a sub-category, which inherits what it leaves out. */
export type Entry = {
  key: string;
  status: Status;
  order?: number;
  icon?: string;
  color?: string;
  /** The set of industry words in the translations (`terms.<set>`). */
  terms?: string;
  client_term?: string;
  booking_modes?: string[];
  cancellation_window_minutes?: number;
  booking_requires_plan?: boolean;
  /** The health declaration clients sign before booking (app/health.py FORMS), if any. */
  health_form?: string | null;
  default_preset?: string;
  recommended_modules?: string[];
  /** Replaces the parent's client fields. */
  client_fields?: ClientField[];
  /** Added to the client fields it inherits. */
  extra_client_fields?: ClientField[];
  default_services?: DefaultService[];
  default_plans?: DefaultPlan[];
  children?: Entry[];
};

/** An entry with everything inherited filled in. */
export type Vertical = {
  key: string;
  status: Status;
  parent: string | null;
  /** The top-level category this entry belongs to (itself for a category). */
  category: string;
  /** Keys from the category down to this entry, used for text fallback. */
  lineage: string[];
  depth: number;
  icon: Icon;
  color: string;
  terms: string;
  clientTerm: string;
  bookingModes: string[];
  recommendedModules: string[];
  clientFields: ClientField[];
  children: string[];
};

/** The categories in display order (catalog/*.json, gathered by `pnpm verticals:export`). */
export const CATEGORIES: Entry[] = [...CATALOG].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

function mergeFields(inherited: ClientField[], entry: Entry): ClientField[] {
  const base = entry.client_fields ?? inherited;
  const extra = (entry.extra_client_fields ?? []).filter((f) => !base.some((b) => b.key === f.key));
  return [...base, ...extra];
}

function build(): Map<string, Vertical> {
  const all = new Map<string, Vertical>();
  const visit = (entry: Entry, parent: Vertical | null) => {
    const lineage = parent ? [...parent.lineage, entry.key] : [entry.key];
    const vertical: Vertical = {
      key: entry.key,
      status: entry.status,
      parent: parent?.key ?? null,
      category: parent?.category ?? entry.key,
      lineage,
      depth: lineage.length - 1,
      icon: (entry.icon ?? parent?.icon ?? "briefcase") as Icon,
      color: entry.color ?? parent?.color ?? "from-slate-500 to-slate-700",
      terms: entry.terms ?? parent?.terms ?? "",
      clientTerm: entry.client_term ?? parent?.clientTerm ?? "client",
      bookingModes: entry.booking_modes ?? parent?.bookingModes ?? [],
      recommendedModules: entry.recommended_modules ?? parent?.recommendedModules ?? [],
      clientFields: mergeFields(parent?.clientFields ?? [], entry),
      children: (entry.children ?? []).map((child) => child.key),
    };
    all.set(entry.key, vertical);
    for (const child of entry.children ?? []) visit(child, vertical);
  };
  for (const category of CATEGORIES) visit(category, null);
  return all;
}

const VERTICALS = build();

/** Every entry, categories first in display order, each followed by its sub-categories. */
export const ALL_VERTICALS: Vertical[] = [...VERTICALS.values()];

export function vertical(key: string | null | undefined): Vertical | undefined {
  return key ? VERTICALS.get(key) : undefined;
}

export function isVertical(key: string | null | undefined): boolean {
  return vertical(key) !== undefined;
}

/** A business can sign up with it (live or beta). */
export function isOpen(key: string | null | undefined): boolean {
  const found = vertical(key);
  return found !== undefined && found.status !== "planned";
}

/** Top-level categories, in display order. */
export function categories(): Vertical[] {
  return ALL_VERTICALS.filter((v) => v.depth === 0);
}

export function childrenOf(key: string): Vertical[] {
  return (vertical(key)?.children ?? []).map((child) => VERTICALS.get(child)!);
}

/** The translation set of industry words for a business (`terms.<set>`); unknown or missing
 * industries (older cached data) get the first category's words. */
export function termsOf(key: string | null | undefined): string {
  return vertical(key)?.terms || CATEGORIES[0]!.terms!;
}

/**
 * The translation key for one of an entry's texts (`verticals.<key>.<name>`), taken from the
 * entry itself or, when it has none, from the nearest parent that does. `has` is the
 * translator's `t.has`.
 */
export function textKey(key: string, name: string, has: (path: string) => boolean): string {
  const lineage = vertical(key)?.lineage ?? [key];
  for (let i = lineage.length - 1; i >= 0; i--) {
    const path = `verticals.${lineage[i]}.${name}`;
    if (has(path)) return path;
  }
  return `verticals.${lineage[0]}.${name}`;
}
