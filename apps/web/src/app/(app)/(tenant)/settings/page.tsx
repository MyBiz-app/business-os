import { getTranslations } from "next-intl/server";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import { apiAssetUrl } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { coverSrc } from "@/lib/workspace";
import { getTenant } from "@/lib/tenant";

import { CloseSection } from "./close-section";
import { ContactEmails } from "./contact-emails";
import { ExportSection } from "./export-section";
import { LegalReadiness } from "./legal-readiness";
import { removeCover, removeLogo } from "./actions";
import { BrandColorForm, CoverForm, DetailsForm, IdentityForm, LogoForm } from "./settings-forms";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { SupportSection } from "./support-section";
import { WriteToSupport } from "./write-to-support";

export default async function SettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  const { tenant } = context;
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const logo = apiAssetUrl(tenant.logo_url);
  const emails = (await context.api.GET("/contact-emails", { params: context.scope })).data;
  const readiness = (await context.api.GET("/tenants/current/readiness", { params: context.scope })).data;

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { href: "/settings/modules", title: t("modulesLink"), hint: t("modulesHint") },
          { href: "/settings/billing", title: t("billingLink"), hint: t("billingHint") },
          { href: "/settings/integrations", title: t("integrationsLink"), hint: t("integrationsHint") },
          ...(tenant.role === "owner" || tenant.role === "manager"
            ? [{ href: "/settings/audit", title: t("auditLink"), hint: t("auditHint") }]
            : []),
        ].map((link) => (
          <Link key={link.href} href={link.href} className="flex items-center justify-between gap-3 card card-hover p-6">
            <span className="flex flex-col gap-1">
              <span className="text-lg font-semibold">{link.title}</span>
              <span className="text-sm text-muted">{link.hint}</span>
            </span>
            <span aria-hidden="true" className="text-primary-ink rtl:rotate-180">→</span>
          </Link>
        ))}
      </div>

      <section aria-labelledby="details-heading" className="flex flex-col gap-4 card p-6">
        <h2 id="details-heading" className="text-lg font-semibold">
          {t("details")}
        </h2>
        <DetailsForm tenant={tenant} timeZones={Intl.supportedValuesOf("timeZone")} />
      </section>

      {emails && <ContactEmails data={emails} locationId={null} />}

      <section aria-labelledby="identity-heading" className="flex flex-col gap-4 card p-6">
        <div className="flex flex-col gap-1">
          <h2 id="identity-heading" className="text-lg font-semibold">
            {t("identity.title")}
          </h2>
          <p className="text-sm text-muted">{t("identity.subtitle")}</p>
        </div>
        <IdentityForm type={tenant.legal_entity_type ?? null} number={tenant.business_number ?? null} />
      </section>

      {readiness && (
        <section aria-labelledby="readiness-heading" className="flex flex-col gap-4 card p-6">
          <div className="flex flex-col gap-1">
            <h2 id="readiness-heading" className="text-lg font-semibold">
              {t("readiness.title")}
            </h2>
            <p className="text-sm text-muted">{t("readiness.subtitle")}</p>
          </div>
          <LegalReadiness tenant={tenant} readiness={readiness} />
        </section>
      )}

      <section aria-labelledby="brand-heading" className="flex flex-col gap-6 card p-6">
        <div className="flex flex-col gap-1">
          <h2 id="brand-heading" className="text-lg font-semibold">
            {t("brand")}
          </h2>
          <p className="text-sm text-muted">{t("brandHint")}</p>
        </div>
        <BrandColorForm key={tenant.primary_color ?? "default"} color={tenant.primary_color} />

        <div className="flex flex-col gap-3 border-t border-border pt-6">
          <h3 className="font-semibold">{t("logo")}</h3>
          <div className="flex items-center gap-4">
            {logo ? (
              <Image src={logo} alt={t("preview")} width={64} height={64} unoptimized className="size-16 rounded-xl border border-border bg-background object-contain" />
            ) : (
              <span className="text-sm text-muted">{t("noLogo")}</span>
            )}
            {logo && (
              <form action={removeLogo}>
                <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
                  {t("removeLogo")}
                </button>
              </form>
            )}
          </div>
          <LogoForm key={tenant.logo_url ?? "none"} />
        </div>

        <div className="flex flex-col gap-3 border-t border-border pt-6">
          <h3 className="font-semibold">{t("cover")}</h3>
          {tenant.cover_url ? (
            <div className="flex flex-col gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element -- private image route */}
              <img src={coverSrc(tenant.cover_url)} alt={t("preview")} className="aspect-[4/1] w-full rounded-xl border border-border object-cover" />
              <form action={removeCover}>
                <button type="submit" className="btn-ghost px-2 py-1 text-sm text-danger">
                  {t("removeCover")}
                </button>
              </form>
            </div>
          ) : (
            <span className="text-sm text-muted">{t("noCover")}</span>
          )}
          <CoverForm key={tenant.cover_url ?? "none"} />
        </div>
      </section>
      {tenant.role === "owner" && <ExportSection context={context} />}
      {tenant.role === "owner" && <SupportSection context={context} />}
      <WriteToSupport />
      {tenant.role === "owner" && <CloseSection name={tenant.name} />}
    </Container>
  );
}
