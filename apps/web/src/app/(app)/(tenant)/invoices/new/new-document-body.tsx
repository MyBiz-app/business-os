import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import { todayIn } from "@/lib/dates";
import { DOCUMENT_KINDS, canCredit, startableKinds } from "@/lib/issued-documents";
import { toMajorUnits } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { issueDocument } from "../actions";
import { DocumentForm } from "../document-form";

type Params = { [key: string]: string | string[] | undefined };

/** Whether the new document starts from a credit note, for the title. */
export const startsCredit = (params: Params) => typeof params.credit === "string";

/** The new-document form. `credit=<id>` starts a credit note for an invoice, `kind` picks the kind,
 * `client` picks the client. The page and the window share it. */
export async function NewDocumentBody({ params, plain = false }: { params: Params; plain?: boolean }) {
  const t = await getTranslations("invoices");
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const readiness = (await api.GET("/tenants/current/readiness", { params: scope })).data;
  const kinds = startableKinds(tenant.legal_entity_type, readiness?.tax_invoice ?? false);

  let credit;
  if (typeof params.credit === "string") {
    try {
      const original = unwrap(await api.GET("/issued-documents/{document_id}", { params: { ...scope, path: { document_id: params.credit } } }));
      if (!canCredit(original.kind)) notFound();
      credit = {
        id: original.id,
        label: `${t(`kinds.${original.kind}`)} ${original.number}`,
        clientName: original.client_name,
        lines: original.lines.map((l) => ({
          description: l.description,
          quantity: String(l.quantity),
          price: toMajorUnits(l.unit_price, original.currency),
        })),
      };
    } catch (error) {
      if (error instanceof ApiError && (error.status === 404 || error.status === 422)) notFound();
      throw error;
    }
  }

  const clientParam = typeof params.client === "string" ? params.client : undefined;
  const clients = unwrap(await api.GET("/clients", { params: { ...scope, query: { status: "active", limit: 100 } } })).items.map((c) => ({
    id: c.id,
    name: [c.first_name, c.last_name].filter(Boolean).join(" "),
  }));
  if (clientParam && !clients.some((c) => c.id === clientParam)) {
    const { data } = await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: clientParam } } });
    if (data) clients.unshift({ id: data.id, name: [data.first_name, data.last_name].filter(Boolean).join(" ") });
  }
  const requested = DOCUMENT_KINDS.find((k) => k === params.kind);
  const kind = requested && kinds.includes(requested) ? requested : kinds[0]!;

  return (
    <>
        {!credit && kinds.length < 4 && (
          <p role="note" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm">
            {tenant.legal_entity_type === "exempt_dealer" ? t("exemptNote") : t("taxNotReady")}{" "}
            {tenant.legal_entity_type !== "exempt_dealer" && (
              <Link href="/settings/business" className="font-semibold text-foreground underline underline-offset-4">{t("completeDetails")}</Link>
            )}
          </p>
        )}
        <section className={plain ? undefined : "card p-6"}>
          <DocumentForm
            action={issueDocument}
            kinds={kinds}
            kind={credit ? "credit_note" : kind}
            currency={tenant.currency}
            clients={clients}
            clientId={clientParam}
            credit={credit}
            today={todayIn(tenant.time_zone)}
          />
        </section>
    </>
  );
}
