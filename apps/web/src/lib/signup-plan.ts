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
  | "social_studio"
  | "pack_plus"
  | "pack_max"
  | "support_priority"
  | "support_vip"
  | "setup_guided"
  | "setup_full"
  | "extra_location";
export type Modules = Partial<Record<ModuleKey, number>>;

/** The legal form of the business, asked in the journey (the API's `legal_entity_type`). */
export const ENTITY_TYPES = ["company", "licensed_dealer", "exempt_dealer", "nonprofit", "partnership", "other"] as const;
export type EntityType = (typeof ENTITY_TYPES)[number];

/** The website step: the business has one (and pastes its address), needs none, or asks MyBiz to
 * build it. */
export const SITE_CHOICES = ["have", "none", "build"] as const;
export type SiteChoice = (typeof SITE_CHOICES)[number];

/** `full`: the system (the usual sign-up). `website_only`: a business that ordered a website and
 * nothing else; it can add the system later without signing up again. */
export type Track = "full" | "website_only";

/** How big the business said it is, kept with the business (the API's `business_size`). */
export type BusinessSize = "solo" | "small" | "medium" | "network";

/** The size bucket of the people and branches asked in the journey: alone, 2-5, 6-20, or a
 * network (more than one branch). */
export function businessSize(staff: number, locations: number): BusinessSize {
  if (locations > 1) return "network";
  if (staff <= 1) return "solo";
  return staff <= 5 ? "small" : staff <= 20 ? "medium" : "network";
}

/** A website address typed or pasted by a person ("www.x.co.il", "https://x.co.il/"), as the https
 * address the API keeps; null if it is not an address. */
export function normalizeWebsiteUrl(value: string): string | null {
  const typed = value.trim();
  if (!typed || /\s/.test(typed)) return null;
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(typed) ? typed : `https://${typed}`);
    if ((url.protocol !== "https:" && url.protocol !== "http:") || !url.hostname.includes(".")) return null;
    const address = url.toString();
    return address.length <= 300 ? address : null;
  } catch {
    return null;
  }
}

export type SignupPlan = {
  /** A catalog industry open for sign-up (category or sub-category). */
  vertical: string;
  name: string;
  clients: number;
  staff: number;
  locations: number;
  currency: Currency;
  modules: Modules;
  /** Company registration number (ח.פ.): required for Israeli (ILS) businesses, optional elsewhere. */
  businessNumber?: string;
  /** Legal form: required in Israel (ILS), where it decides which documents the business issues. */
  entityType?: EntityType;
  /** The website step: has one, needs none, or wants MyBiz to build it. */
  site?: SiteChoice;
  /** The address of the website the business already has (with `site: "have"`). */
  websiteUrl?: string;
  /** Left out for the usual sign-up. */
  track?: Track;
};

/** The Israeli ID / company number check digit (the same rule as the API): up to 9 digits. */
export function israeliNumberValid(number: string): boolean {
  if (!/^\d{1,9}$/.test(number)) return false;
  let total = 0;
  [...number.padStart(9, "0")].forEach((digit, index) => {
    const value = Number(digit) * (1 + (index % 2));
    total += value > 9 ? value - 9 : value;
  });
  return total % 10 === 0 && Number(number) > 0;
}

/** Digits only (people type spaces or dashes). */
export const cleanBusinessNumber = (value: string) => value.replace(/[\s-]/g, "");

/** Whether the number may be submitted: required with a check digit in Israel, optional (up to 20
 * characters) abroad. */
export function businessNumberOk(currency: Currency, value: string): boolean {
  const number = cleanBusinessNumber(value);
  if (currency === "ILS") return israeliNumberValid(number);
  return number.length <= 20;
}

/** Israeli companies (ח.פ.) are registered under numbers starting with 51; anything else is
 * only a soft warning, never a block. */
export function companyPrefixWarning(currency: Currency, entityType: EntityType | undefined, value: string): boolean {
  const number = cleanBusinessNumber(value);
  return currency === "ILS" && entityType === "company" && israeliNumberValid(number) && !number.padStart(9, "0").startsWith("51");
}

/** The choices on each add-on screen, from the basic one up (2-4 per screen, decision X16).
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

/** What a website built by MyBiz costs: once, and a month (minor units). */
export type SiteFee = { setup: number; monthly: number };
/** The two website price lists: on its own, and with the system. */
export type SiteFees = { alone: SiteFee; withSystem: SiteFee };

/** The API's website price list (`/public/website-prices`) as the two fees the cart needs. */
export function websiteFees(prices: { landing_only: SiteFee; landing_with_system: SiteFee } | null | undefined): SiteFees | undefined {
  return prices ? { alone: prices.landing_only, withSystem: prices.landing_with_system } : undefined;
}

type CatalogLike = {
  /** Where the website fees go; without them a website adds no price lines. */
  website?: SiteFees;
  core: { up_to_clients?: number | null; price: number }[];
  modules: CatalogModuleLike[];
};

export type PriceLine = { key: "core" | "website" | ModuleKey; quantity: number; amount: number };

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
  "social_studio",
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
  plan: Pick<SignupPlan, "clients" | "modules"> & Partial<Pick<SignupPlan, "site" | "track">>,
): { lines: PriceLine[]; total: number; once: PriceLine[]; onceTotal: number } {
  const byKey = Object.fromEntries(catalog.modules.map((m) => [m.key, m]));
  const websiteOnly = plan.track === "website_only";
  // A website-only business has no system, so no core plan and no modules.
  const lines: PriceLine[] = websiteOnly ? [] : [{ key: "core", quantity: 1, amount: coreTier(catalog, plan.clients).price }];
  const once: PriceLine[] = [];
  for (const key of websiteOnly ? [] : MODULE_KEYS) {
    const quantity = plan.modules[key] ?? 0;
    const entry = byKey[key];
    if (quantity > 0 && entry) (entry.billing === "once" ? once : lines).push({ key, quantity, amount: entry.price * quantity });
  }
  // The website MyBiz builds: a monthly fee and a one-time setup (cheaper with the system).
  const price = catalog.website?.[websiteOnly ? "alone" : "withSystem"];
  if (price && (plan.site === "build" || websiteOnly)) {
    lines.push({ key: "website", quantity: 1, amount: price.monthly });
    once.push({ key: "website", quantity: 1, amount: price.setup });
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
  const number = typeof raw.businessNumber === "string" ? cleanBusinessNumber(raw.businessNumber) : "";
  const entityType = (ENTITY_TYPES as readonly unknown[]).includes(raw.entityType) ? (raw.entityType as EntityType) : undefined;
  const site = (SITE_CHOICES as readonly unknown[]).includes(raw.site) ? (raw.site as SiteChoice) : undefined;
  const websiteUrl = typeof raw.websiteUrl === "string" && site === "have" ? normalizeWebsiteUrl(raw.websiteUrl) : null;
  const track: Track | undefined = raw.track === "website_only" ? "website_only" : undefined;
  return {
    vertical: raw.vertical,
    name,
    clients: raw.clients as number,
    staff: raw.staff as number,
    locations: raw.locations as number,
    currency: raw.currency as Currency,
    modules,
    ...(number && number.length <= 20 ? { businessNumber: number } : {}),
    ...(entityType ? { entityType } : {}),
    ...(site ? { site } : {}),
    ...(websiteUrl ? { websiteUrl } : {}),
    ...(track ? { track } : {}),
  };
}

/** The core tier a client count lands in (100 / 300 / 1000, or 1500 for "1,000+"). */
export function clientsTier(clients: number): (typeof CLIENT_SIZES)[number] {
  return CLIENT_SIZES.find((size) => size < 1500 && clients <= size) ?? 1500;
}

/** The pricing calculator's plan as a /start link: the business starts the journey with
 * everything already chosen (`from=calc` opens it at the business details, then the summary). */
export function calcPlanQuery(plan: Pick<SignupPlan, "clients" | "locations" | "currency" | "modules"> & { vertical?: string | null }): string {
  const modules = MODULE_KEYS.filter((key) => key !== "extra_location" && plan.modules[key]);
  const params = new URLSearchParams({ from: "calc", currency: plan.currency, clients: String(plan.clients), locations: String(plan.locations) });
  if (plan.vertical) params.set("vertical", plan.vertical);
  if (modules.length > 0) params.set("modules", modules.join(","));
  return params.toString();
}

/** The modules named in a /start link's `modules` parameter (unknown keys are dropped). */
export function modulesFromParam(value: unknown): Modules {
  if (typeof value !== "string") return {};
  return Object.fromEntries(value.split(",").filter((key): key is ModuleKey => (MODULE_KEYS as readonly string[]).includes(key)).map((key) => [key, 1]));
}

/** A whole number from a link parameter, within bounds, else the fallback. */
export function wholeParam(value: unknown, min: number, max: number, fallback: number): number {
  const number = typeof value === "string" && /^\d{1,6}$/.test(value) ? Number(value) : NaN;
  return Number.isInteger(number) && number >= min && number <= max ? number : fallback;
}
