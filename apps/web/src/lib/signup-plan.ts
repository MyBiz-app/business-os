/** The plan a business owner builds in the sign-up journey (/start), carried to the payment
 * step (/start/finish) in the URL, so it survives the email confirmation in between. The API
 * validates and prices the modules again when the business is created; this is the preview. */
import { isOpen } from "@business-os/verticals";

export const CURRENCIES = ["ILS", "USD", "EUR"] as const;
/** Active-client sizes offered in the journey (the core plan's tiers; 1500 means 1,000+). */
export const CLIENT_SIZES = [100, 300, 1000, 1500] as const;
/** The add-ons offered one per screen, in order: the product's modules, then the extras
 * (bigger bundle, better support, setup by the team). */
export const OFFERS = ["client_app", "ai", "crm", "whatsapp", "pack", "support", "setup"] as const;

export type Currency = (typeof CURRENCIES)[number];
export type Offer = (typeof OFFERS)[number];
export type ModuleKey =
  | "client_app"
  | "client_app_branded"
  | "ai_basic"
  | "ai_pro"
  | "crm"
  | "crm_automation"
  | "whatsapp"
  | "whatsapp_ai"
  | "pack_plus"
  | "pack_max"
  | "support_priority"
  | "support_vip"
  | "setup_guided"
  | "setup_full"
  | "extra_location";
export type Modules = Partial<Record<ModuleKey, number>>;

export type SignupPlan = {
  /** A catalog industry open for sign-up (category or sub-category). */
  vertical: string;
  name: string;
  clients: number;
  staff: number;
  locations: number;
  currency: Currency;
  modules: Modules;
};

/** The choices on each add-on screen, from the basic one up (2–4 per screen, decision X16).
 * A tier with no modules is what every plan already has ("included"). Prices come from the
 * catalog, so they change in one place (apps/api/app/commerce/modules.py). */
export const OFFER_TIERS: Record<Offer, { key: string; modules: ModuleKey[] }[]> = {
  client_app: [
    { key: "basic", modules: ["client_app"] },
    { key: "pro", modules: ["client_app", "client_app_branded"] },
  ],
  ai: [
    { key: "basic", modules: ["ai_basic"] },
    { key: "pro", modules: ["ai_pro"] },
  ],
  crm: [
    { key: "basic", modules: ["crm"] },
    { key: "pro", modules: ["crm", "crm_automation"] },
  ],
  whatsapp: [
    { key: "basic", modules: ["whatsapp"] },
    { key: "pro", modules: ["whatsapp", "whatsapp_ai"] },
  ],
  pack: [
    { key: "included", modules: [] },
    { key: "plus", modules: ["pack_plus"] },
    { key: "max", modules: ["pack_max"] },
  ],
  support: [
    { key: "standard", modules: [] },
    { key: "priority", modules: ["support_priority"] },
    { key: "vip", modules: ["support_vip"] },
  ],
  setup: [
    { key: "self", modules: [] },
    { key: "guided", modules: ["setup_guided"] },
    { key: "full", modules: ["setup_full"] },
  ],
};

type CatalogModuleLike = {
  key: string;
  price: number;
  billing?: "monthly" | "once";
  requires_any?: string[];
  requires_all?: string[];
};

type CatalogLike = {
  core: { up_to_clients?: number | null; price: number }[];
  modules: CatalogModuleLike[];
};

export type PriceLine = { key: "core" | ModuleKey; quantity: number; amount: number };

const offerModules = (offer: Offer) => new Set(OFFER_TIERS[offer].flatMap((tier) => tier.modules));

/** The tier of an add-on in the plan (the highest one whose modules are all in), or null. */
export function tierOf(offer: Offer, modules: Modules): string | null {
  const tiers = OFFER_TIERS[offer].filter((tier) => tier.modules.length > 0);
  return [...tiers].reverse().find((tier) => tier.modules.every((key) => modules[key]))?.key ?? null;
}

/** Drops modules whose requirements left the plan (e.g. the branded app without the app). */
export function withoutOrphans(modules: Modules, catalog: CatalogLike): Modules {
  const next = { ...modules };
  let changed = true;
  while (changed) {
    changed = false;
    for (const entry of catalog.modules) {
      if (!next[entry.key as ModuleKey]) continue;
      const missingAll = (entry.requires_all ?? []).some((key) => !next[key as ModuleKey]);
      const missingAny = (entry.requires_any ?? []).length > 0 && !(entry.requires_any ?? []).some((key) => next[key as ModuleKey]);
      if (missingAll || missingAny) {
        delete next[entry.key as ModuleKey];
        changed = true;
      }
    }
  }
  return next;
}

/** The plan with an add-on set to one tier (null: none of it). What a tier needs comes along:
 * AI replies on WhatsApp bring AI Basic when the plan has no AI yet. */
export function chooseTier(offer: Offer, tier: string | null, modules: Modules, catalog: CatalogLike): Modules {
  const next = { ...modules };
  for (const key of offerModules(offer)) delete next[key];
  for (const key of OFFER_TIERS[offer].find((t) => t.key === tier)?.modules ?? []) {
    next[key] = 1;
    const entry = catalog.modules.find((m) => m.key === key);
    const any = entry?.requires_any ?? [];
    if (any.length > 0 && !any.some((k) => next[k as ModuleKey])) next[any[0] as ModuleKey] = 1;
  }
  return withoutOrphans(next, catalog);
}

/** What a tier adds to the monthly price (or the one-time price, for a service). */
export function tierPrice(offer: Offer, tier: string, catalog: CatalogLike): number {
  const modules = OFFER_TIERS[offer].find((t) => t.key === tier)?.modules ?? [];
  return modules.reduce((sum, key) => sum + (catalog.modules.find((m) => m.key === key)?.price ?? 0), 0);
}

export const isOnce = (offer: Offer) => offer === "setup";

export const TRIAL_DAYS = 14;

/** The trial's last day for a business created now (YYYY-MM-DD). */
export function trialEndsOn(now: Date = new Date()): string {
  return new Date(now.getTime() + TRIAL_DAYS * 86_400_000).toISOString().slice(0, 10);
}

const MODULE_KEYS: readonly ModuleKey[] = [
  "client_app",
  "client_app_branded",
  "ai_basic",
  "ai_pro",
  "crm",
  "crm_automation",
  "whatsapp",
  "whatsapp_ai",
  "pack_plus",
  "pack_max",
  "support_priority",
  "support_vip",
  "extra_location",
  "setup_guided",
  "setup_full",
];

/** Every location after the first is a paid extra location. */
export function withLocations(modules: Modules, locations: number): Modules {
  const next = { ...modules };
  if (locations > 1) next.extra_location = Math.min(locations - 1, 50);
  else delete next.extra_location;
  return next;
}

export function coreTier<T extends CatalogLike["core"][number]>(catalog: { core: T[] }, clients: number): T {
  return catalog.core.find((tier) => tier.up_to_clients == null || clients <= tier.up_to_clients) ?? catalog.core[0];
}

/** The monthly lines and total (the core first, then modules in a stable order), and apart
 * from them the one-time services, charged with the first invoice after the trial. */
export function priceLines(
  catalog: CatalogLike,
  plan: Pick<SignupPlan, "clients" | "modules">,
): { lines: PriceLine[]; total: number; once: PriceLine[]; onceTotal: number } {
  const byKey = Object.fromEntries(catalog.modules.map((m) => [m.key, m]));
  const lines: PriceLine[] = [{ key: "core", quantity: 1, amount: coreTier(catalog, plan.clients).price }];
  const once: PriceLine[] = [];
  for (const key of MODULE_KEYS) {
    const quantity = plan.modules[key] ?? 0;
    const entry = byKey[key];
    if (quantity > 0 && entry) (entry.billing === "once" ? once : lines).push({ key, quantity, amount: entry.price * quantity });
  }
  const sum = (list: PriceLine[]) => list.reduce((total, line) => total + line.amount, 0);
  return { lines, total: sum(lines), once, onceTotal: sum(once) };
}

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): string {
  const binary = atob(value.replaceAll("-", "+").replaceAll("_", "/"));
  return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
}

export function encodePlan(plan: SignupPlan): string {
  return toBase64Url(JSON.stringify(plan));
}

const whole = (value: unknown, min: number, max: number) =>
  typeof value === "number" && Number.isInteger(value) && value >= min && value <= max;

/** The plan from the URL, or null if it is missing or not a plan. */
export function decodePlan(value: unknown): SignupPlan | null {
  if (typeof value !== "string" || value.length > 2000) return null;
  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(fromBase64Url(value));
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const name = typeof raw.name === "string" ? raw.name.trim() : "";
  if (
    typeof raw.vertical !== "string" ||
    !isOpen(raw.vertical) ||
    !(CURRENCIES as readonly unknown[]).includes(raw.currency) ||
    !name ||
    name.length > 120 ||
    !whole(raw.clients, 0, 100_000) ||
    !whole(raw.staff, 1, 500) ||
    !whole(raw.locations, 1, 51) ||
    typeof raw.modules !== "object" ||
    raw.modules === null
  ) {
    return null;
  }
  const modules: Modules = {};
  for (const [key, quantity] of Object.entries(raw.modules)) {
    if (!(MODULE_KEYS as readonly string[]).includes(key) || !whole(quantity, 1, 50)) return null;
    modules[key as ModuleKey] = quantity as number;
  }
  return {
    vertical: raw.vertical,
    name,
    clients: raw.clients as number,
    staff: raw.staff as number,
    locations: raw.locations as number,
    currency: raw.currency as Currency,
    modules,
  };
}
