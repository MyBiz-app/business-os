/** The plan a business owner builds in the sign-up journey (/start), carried to the payment
 * step (/start/finish) in the URL, so it survives the email confirmation in between. The API
 * validates and prices the modules again when the business is created; this is the preview. */
import { isOpen } from "@business-os/verticals";

export const CURRENCIES = ["ILS", "USD", "EUR"] as const;
/** Active-client sizes offered in the journey (the core plan's tiers; 1500 means 1,000+). */
export const CLIENT_SIZES = [100, 300, 1000, 1500] as const;
/** The add-ons offered one per screen, in order. */
export const OFFERS = ["client_app", "ai", "crm", "whatsapp"] as const;

export type Currency = (typeof CURRENCIES)[number];
export type Offer = (typeof OFFERS)[number];
export type ModuleKey = "client_app" | "ai_basic" | "ai_pro" | "crm" | "whatsapp" | "extra_location";
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

type CatalogLike = {
  core: { up_to_clients?: number | null; price: number }[];
  modules: { key: string; price: number }[];
};

export type PriceLine = { key: "core" | ModuleKey; quantity: number; amount: number };

export const TRIAL_DAYS = 14;

/** The trial's last day for a business created now (YYYY-MM-DD). */
export function trialEndsOn(now: Date = new Date()): string {
  return new Date(now.getTime() + TRIAL_DAYS * 86_400_000).toISOString().slice(0, 10);
}

const MODULE_KEYS: readonly ModuleKey[] = ["client_app", "ai_basic", "ai_pro", "crm", "whatsapp", "extra_location"];

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

/** The monthly lines and total: the core first, then modules in a stable order. */
export function priceLines(catalog: CatalogLike, plan: Pick<SignupPlan, "clients" | "modules">): { lines: PriceLine[]; total: number } {
  const prices = Object.fromEntries(catalog.modules.map((m) => [m.key, m.price]));
  const lines: PriceLine[] = [{ key: "core", quantity: 1, amount: coreTier(catalog, plan.clients).price }];
  for (const key of MODULE_KEYS) {
    const quantity = plan.modules[key] ?? 0;
    if (quantity > 0 && key in prices) lines.push({ key, quantity, amount: prices[key] * quantity });
  }
  return { lines, total: lines.reduce((sum, line) => sum + line.amount, 0) };
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
