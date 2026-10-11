import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getPlatform } from "@/lib/platform";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.integrations");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The platform's providers (X13): the default per capability, the providers available, and how
 * many businesses connected their own. Defaults change in the environment (API_<CAP>_PROVIDER). */
export default async function PlatformIntegrationsPage() {
  const t = await getTranslations("platform.integrations");
  const tCap = await getTranslations("integrations.capabilities");
  const { api, isOwner } = await getPlatform();
  if (!isOwner) notFound();
  const capabilities = unwrap(await api.GET("/platform/integrations"));
  const title = (capability: string) =>
    ["payments", "invoicing", "messaging"].includes(capability)
      ? tCap(`${capability as "payments"}.title`)
      : t(`capabilities.${capability as "email"}`);

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-muted">{t("subtitle")}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {capabilities.map((capability) => (
          <section key={capability.capability} aria-labelledby={`cap-${capability.capability}`} className="flex flex-col gap-3 card p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id={`cap-${capability.capability}`} className="text-lg font-semibold">
                {title(capability.capability)}
              </h2>
              <Pill tone={capability.builtin ? "warning" : "success"}>
                {capability.builtin ? t("simulated") : t("live")}
              </Pill>
            </div>
            <p className="text-sm">
              {t("default")}: <span className="font-semibold">{capability.default_label}</span>{" "}
              <code dir="ltr" className="text-xs text-muted">({capability.default_provider})</code>
            </p>
            <div className="flex flex-col gap-1 text-sm">
              <span className="text-muted">{t("available")}</span>
              <ul className="flex flex-wrap gap-2">
                {capability.options.map((option) => (
                  <li key={option.name} className="rounded-full border border-border px-3 py-1">
                    {option.label}
                    {capability.businesses_connected[option.name] ? ` · ${t("businesses", { count: capability.businesses_connected[option.name] })}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ))}
      </div>
      <p className="text-sm text-muted">{t("howTo")}</p>
    </main>
  );
}
