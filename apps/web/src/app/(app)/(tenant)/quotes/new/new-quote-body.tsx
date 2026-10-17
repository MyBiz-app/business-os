import { getTranslations } from "next-intl/server";

import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

import { createQuote } from "../actions";
import { QuoteForm } from "../quote-form";

/** The new-quote form; `client` picks the client (from the client's card). The page and the window share it. */
export async function NewQuoteBody({ client, example = false, plain = false }: { client?: string | string[]; example?: boolean; plain?: boolean }) {
  const t = await getTranslations("quotes");
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const page = unwrap(await api.GET("/clients", { params: { ...scope, query: { status: "active", limit: 100 } } }));
  const clients = page.items.map((c) => ({ id: c.id, name: [c.first_name, c.last_name].filter(Boolean).join(" ") }));
  // From a client's card: that client, even beyond the first hundred.
  if (typeof client === "string" && !clients.some((c) => c.id === client)) {
    const { data } = await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: client } } });
    if (data) clients.unshift({ id: data.id, name: [data.first_name, data.last_name].filter(Boolean).join(" ") });
  }

  return (
    <section className={plain ? undefined : "card p-6"}>
      <QuoteForm
        action={createQuote}
        currency={tenant.currency}
        clients={clients}
        clientId={typeof client === "string" ? client : undefined}
        submitLabel={t("saveDraft")}
        defaults={{
          title: example ? t("example.title") : "",
          lines: example
            ? [
                { description: t("example.line1"), quantity: "1", price: "1500" },
                { description: t("example.line2"), quantity: "1", price: "150" },
              ]
            : [],
          deposit_percent: 30,
          valid_until: addDays(todayIn(tenant.time_zone), 14),
          event_date: "",
          event_time: "",
          event_place: "",
          notes: example ? t("example.notes") : "",
        }}
      />
    </section>
  );
}
