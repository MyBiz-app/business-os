import { CreditCard, FileText, MessageCircle, Plug } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { disconnectProvider } from "./actions";
import { ProviderForm } from "./provider-form";

const ICONS = { payments: CreditCard, invoicing: FileText, messaging: MessageCircle } as const;

/** Settings → Integrations (X13): the business's payment, invoicing and messaging providers.
 * Switching provider is choosing another one here; nothing else in the business changes. */
export default async function IntegrationsPage() {
  const t = await getTranslations("integrations");
  const tSettings = await getTranslations("settings");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const integrations = unwrap(await api.GET("/integrations", { params: scope }));
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/settings" className="text-sm text-primary underline-offset-4 hover:underline">
        {tSettings("title")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="flex items-center gap-2 text-3xl font-bold">
          <Plug aria-hidden="true" className="size-7 text-primary" />
          {t("title")}
        </h1>
        <p className="text-sm text-muted">{t("subtitle")}</p>
      </div>
      {integrations.map((integration) => {
        const Icon = ICONS[integration.capability];
        const heading = `integration-${integration.capability}`;
        return (
          <section key={integration.capability} aria-labelledby={heading} className="flex flex-col gap-4 card p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id={heading} className="flex items-center gap-2 text-lg font-semibold">
                <Icon aria-hidden="true" className="size-5 text-primary" />
                {t(`capabilities.${integration.capability}.title`)}
              </h2>
              <Pill tone={integration.builtin ? "muted" : "success"}>{integration.provider_label}</Pill>
            </div>
            <p className="text-sm text-muted">{t(`capabilities.${integration.capability}.hint`)}</p>
            <p className="text-sm">
              {integration.own
                ? t("connectedOn", { date: integration.connected_at ? date.format(new Date(integration.connected_at)) : "" })
                : t("platformDefault")}
            </p>
            <details>
              <summary className="cursor-pointer text-sm font-medium text-primary">{t("change")}</summary>
              <div className="pt-4">
                <ProviderForm integration={integration} />
              </div>
            </details>
            {integration.own && (
              <form action={disconnectProvider.bind(null, integration.capability)}>
                <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                  {t("disconnect")}
                </button>
              </form>
            )}
          </section>
        );
      })}
    </main>
  );
}
