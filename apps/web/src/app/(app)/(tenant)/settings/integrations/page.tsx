import { CreditCard, FileText, MessageCircle } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";

import { disconnectProvider } from "./actions";
import { ProviderForm } from "./provider-form";

const ICONS = { payments: CreditCard, invoicing: FileText, messaging: MessageCircle } as const;

/** Settings → Integrations (X13): the business's payment, invoicing and messaging providers.
 * Switching provider is choosing another one here; nothing else in the business changes. */
export default async function IntegrationsPage() {
  const t = await getTranslations("integrations");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const integrations = unwrap(await api.GET("/integrations", { params: scope }));
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("title")} description={t("subtitle")} />
      {integrations.map((integration) => {
        const Icon = ICONS[integration.capability];
        const heading = `integration-${integration.capability}`;
        return (
          <section key={integration.capability} aria-labelledby={heading} className="flex flex-col gap-4 card p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id={heading} className="flex items-center gap-2 text-lg font-semibold">
                <Icon aria-hidden="true" className="size-5 text-primary-ink" />
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
              <summary className="cursor-pointer text-sm font-medium text-primary-ink">{t("change")}</summary>
              <div className="pt-4">
                <ProviderForm integration={integration} />
              </div>
            </details>
            {integration.own && (
              <form action={disconnectProvider.bind(null, integration.capability)}>
                <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
                  {t("disconnect")}
                </button>
              </form>
            )}
          </section>
        );
      })}
    </div>
  );
}
