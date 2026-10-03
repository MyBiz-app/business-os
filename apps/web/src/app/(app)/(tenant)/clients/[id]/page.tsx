import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { canWriteClients } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { updateClient } from "../actions";
import { ClientForm } from "../client-form";
import { StatusBadge } from "../status-badge";

export default async function ClientPage({ params }: PageProps<"/clients/[id]">) {
  const { id } = await params;
  const t = await getTranslations("clients");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();

  const { data: client } = await api.GET("/clients/{client_id}", {
    params: { ...scope, path: { client_id: id } },
  });
  if (!client) notFound();

  const joined = new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: tenant.time_zone }).format(
    new Date(client.created_at),
  );
  const writable = canWriteClients(tenant.role);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/clients" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold">{[client.first_name, client.last_name].filter(Boolean).join(" ")}</h1>
        <StatusBadge status={client.status} />
      </div>
      <p className="text-sm text-muted">{t("joined", { date: joined })}</p>

      <section aria-labelledby="details-heading" className="rounded-2xl border border-border bg-surface p-6">
        <h2 id="details-heading" className="mb-4 text-lg font-semibold">
          {t("details")}
        </h2>
        <ClientForm
          action={updateClient.bind(null, client.id)}
          client={client}
          submitLabel={t("save")}
          readOnly={!writable}
        />
      </section>
    </main>
  );
}
