import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { updateService } from "../actions";
import { ServiceForm } from "../service-form";

export default async function ServicePage({ params }: PageProps<"/services/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: service } = await api.GET("/services/{service_id}", {
    params: { ...scope, path: { service_id: id } },
  });
  if (!service) notFound();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/services" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <h1 className="text-3xl font-bold">{service.name}</h1>
      <ServiceForm
        action={updateService.bind(null, service.id)}
        service={service}
        currency={service.price_currency}
        submitLabel={t("common.save")}
        readOnly={!canWriteCatalog(tenant)}
      />
    </main>
  );
}
