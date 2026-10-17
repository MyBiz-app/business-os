import { toMinorUnits } from "@business-os/i18n/money";

export const DOCUMENT_KINDS = ["tax_invoice_receipt", "tax_invoice", "credit_note", "quote", "transaction_invoice"] as const;
export type DocumentKind = (typeof DOCUMENT_KINDS)[number];
export type PaymentMethod = "card" | "cash" | "transfer" | "other";
export const PAYMENT_METHODS: readonly PaymentMethod[] = ["card", "cash", "transfer", "other"];

const TAX_KINDS: readonly DocumentKind[] = ["tax_invoice_receipt", "tax_invoice", "credit_note"];

export type IssueBody = {
  kind: DocumentKind;
  client_id?: string;
  client_name?: string;
  client_email?: string;
  client_tax_id?: string;
  lines: { description: string; quantity: number; unit_price: number }[];
  payment_method?: PaymentMethod;
  due_date?: string;
  valid_until?: string;
  payment_terms?: string;
  notes?: string;
  reference_id?: string;
};

/** The kinds a business can start from the "new document" screen. Exempt dealers get no tax
 * document (the API refuses it too); a credit note starts from an invoice, never from scratch. */
export function startableKinds(entityType: string | null | undefined, taxReady: boolean): DocumentKind[] {
  return DOCUMENT_KINDS.filter((kind) => {
    if (kind === "credit_note") return false;
    if (!TAX_KINDS.includes(kind)) return true;
    return entityType !== "exempt_dealer" && taxReady;
  });
}

/** Only an invoice can be credited. */
export function canCredit(kind: DocumentKind): boolean {
  return kind === "tax_invoice" || kind === "tax_invoice_receipt";
}

/** The editor's values: lines come as line.<i>.description / quantity / price (major units).
 * Returns null when nothing usable was entered. */
export function readIssueBody(formData: FormData, currency: string): IssueBody | null {
  const value = (name: string) => String(formData.get(name) ?? "").trim();
  const kind = DOCUMENT_KINDS.find((k) => k === value("kind"));
  if (!kind) return null;
  const indexes = new Set<number>();
  for (const name of formData.keys()) {
    const match = /^line\.(\d+)\./.exec(name);
    if (match) indexes.add(Number(match[1]));
  }
  const lines = [...indexes]
    .sort((a, b) => a - b)
    .map((i) => ({
      description: value(`line.${i}.description`),
      quantity: Number(value(`line.${i}.quantity`) || "1"),
      unit_price: toMinorUnits(value(`line.${i}.price`) || "0", currency),
    }))
    .filter((line) => line.description);
  if (lines.length === 0 || lines.some((l) => l.unit_price === null || !(l.quantity > 0))) return null;
  const optional = (name: string) => value(name) || undefined;
  const method = PAYMENT_METHODS.find((m) => m === value("payment_method"));
  const body: IssueBody = {
    kind,
    lines: lines as IssueBody["lines"],
    client_id: optional("client_id"),
    client_name: optional("client_name"),
    client_email: optional("client_email"),
    client_tax_id: optional("client_tax_id"),
    payment_method: method,
    due_date: optional("due_date"),
    valid_until: optional("valid_until"),
    payment_terms: optional("payment_terms"),
    notes: optional("notes"),
    reference_id: optional("reference_id"),
  };
  if (kind === "credit_note") return body.reference_id ? body : null;
  if (!body.client_id && !body.client_name) return null;
  if (kind === "tax_invoice_receipt" && !body.payment_method) return null;
  return body;
}
