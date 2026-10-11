import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";

import { createQuote } from "../actions";
import { QuoteForm } from "../quote-form";

/** A new quote; `?client=` picks the client (from the client's card). */
export default async function NewQuotePage({ searchParams }: PageProps<"/quotes/new">) {
  const t = await getTranslations("quotes");
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const client = (await searchParams).client;
  const page = unwrap(await api.GET("/clients", { params: { ...scope, query: { status: "active", limit: 100 } } }));
  const clients = page.items.map((c) => ({ id: c.id, name: [c.first_name, c.last_name].filter(Boolean).join(" ") }));
  // From a client's card: that client, even beyond the first hundred.
  if (typeof client === "string" && !clients.some((c) => c.id === client)) {
    const { data } = await api.GET("/clients/{client_id}", { params: { ...scope, path: { client_id: client } } });
    if (data) clients.unshift({ id: data.id, name: [data.first_name, data.last_name].filter(Boolean).join(" ") });
  }

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <Link href="/quotes" className="text-sm text-primary underline-offset-4 hover:underline">{t("back")}</Link>
      <h1 className="text-3xl font-bold">{t("new")}</h1>
      <section className="card p-6">
        <QuoteForm
          action={createQuote}
          currency={tenant.currency}
          clients={clients}
          clientId={typeof client === "string" ? client : undefined}
          submitLabel={t("saveDraft")}
          defaults={{
            title: "",
            lines: [],
            deposit_percent: 30,
            valid_until: addDays(todayIn(tenant.time_zone), 14),
            event_date: "",
            event_time: "",
            event_place: "",
            notes: "",
          }}
        />
      </section>
    </main>
  );
}
