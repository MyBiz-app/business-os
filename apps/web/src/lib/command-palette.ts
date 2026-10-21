// The pure parts of the Cmd+K window: what a hit links to, which quick actions a person may start,
// how a typed text is matched against pages and actions, and the "recent" list kept in the browser.
import { hasUpgrade } from "./upgrades.ts";

export type HitKind = "client" | "lead" | "staff" | "session" | "invoice";

/** One result of the API's /search, ready to show: the texts are already in the person's language. */
export type PaletteHit = { kind: HitKind; id: string; title: string; meta: string; href: string };

/** Where a record opens. */
export function hitHref(kind: HitKind, id: string): string {
  switch (kind) {
    case "client":
      return `/clients/${id}`;
    case "lead":
      return `/leads/${id}`;
    case "staff":
      return `/team/${id}`;
    case "session":
      return `/schedule/${id}`;
    case "invoice":
      return `/invoices/${id}`;
  }
}

type ApiHit = {
  kind: HitKind;
  id: string;
  title: string;
  subtitle?: string | null;
  tag?: string | null;
  at?: string | null;
  number?: number | null;
};

/** Names for the small tags the API sends (a lead's stage, a person's role, a document's kind). */
export type HitLabels = {
  stage: Record<string, string>;
  role: Record<string, string>;
  document: Record<string, string>;
  /** A class's start in the business's time zone. */
  when: (instant: string) => string;
};

const join = (...parts: (string | null | undefined | false)[]) => parts.filter(Boolean).join(" · ");

/** The line under a hit's title, by kind. */
export function toPaletteHit(hit: ApiHit, labels: HitLabels): PaletteHit {
  const tag = hit.tag ?? "";
  const meta = {
    client: () => join(hit.subtitle),
    lead: () => join(labels.stage[tag], hit.subtitle),
    staff: () => join(labels.role[tag], hit.subtitle),
    session: () => join(hit.at && labels.when(hit.at), hit.subtitle),
    invoice: () => join(labels.document[tag], hit.number != null && `#${hit.number}`, hit.at && labels.when(hit.at)),
  }[hit.kind]();
  return { kind: hit.kind, id: hit.id, title: hit.title, meta, href: hitHref(hit.kind, hit.id) };
}

export type QuickActionId = "newClient" | "newLead" | "bookAppointment" | "newSession" | "newQuote" | "newInvoice";
export type QuickAction = { id: QuickActionId; href: string };

/** The things worth starting from the keyboard, only for what the person may open. The API checks
 * each again; this keeps the window from offering what it would refuse. */
export function quickActionsFor(permissions: readonly string[], modules: readonly string[]): QuickAction[] {
  const can = (permission: string) => permissions.includes(permission);
  const actions: (QuickAction | false)[] = [
    can("clients.write") && { id: "newClient", href: "/clients/new" },
    can("clients.write") && hasUpgrade(modules, "crm") && { id: "newLead", href: "/leads/new" },
    can("bookings.manage") && can("schedule.read") && { id: "bookAppointment", href: "/schedule/appointment" },
    can("schedule.write") && { id: "newSession", href: "/schedule/new" },
    can("sales.manage") && { id: "newQuote", href: "/quotes/new" },
    can("sales.manage") && { id: "newInvoice", href: "/invoices/new" },
  ];
  return actions.filter((action): action is QuickAction => action !== false);
}

/** Lower case, without accents or Hebrew vowel points, so "cafe" finds "Café". */
export function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
}

/** Every typed word appears somewhere in the label (order does not matter). */
export function matches(label: string, query: string): boolean {
  const words = fold(query).split(/\s+/).filter(Boolean);
  const target = fold(label);
  return words.length > 0 && words.every((word) => target.includes(word));
}

export const MAX_RECENTS = 5;
export const MIN_SEARCH_LENGTH = 2;

function isHit(value: unknown): value is PaletteHit {
  const v = value as Partial<PaletteHit> | null;
  return (
    typeof v?.id === "string" &&
    typeof v.title === "string" &&
    typeof v.meta === "string" &&
    typeof v.href === "string" &&
    ["client", "lead", "staff", "session", "invoice"].includes(String(v.kind)) &&
    // A stored link is only ever a path of this site.
    /^\/(?!\/)/.test(v.href)
  );
}

export function parseRecents(raw: string | null): PaletteHit[] {
  try {
    const parsed: unknown = JSON.parse(raw ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isHit).slice(0, MAX_RECENTS) : [];
  } catch {
    return [];
  }
}

/** The opened record goes to the top; the same record is never listed twice. */
export function withRecent(list: readonly PaletteHit[], hit: PaletteHit): PaletteHit[] {
  return [hit, ...list.filter((item) => !(item.kind === hit.kind && item.id === hit.id))].slice(0, MAX_RECENTS);
}
