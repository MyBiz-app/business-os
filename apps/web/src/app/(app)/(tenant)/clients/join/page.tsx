import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import QRCode from "qrcode";

import { siteOrigin } from "@/lib/origin";
import { getTenantFor } from "@/lib/tenant";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

/** The business's join code and QR code, to print for the front desk or share. */
export default async function JoinCodePage() {
  const t = await getTranslations("join");
  const term = await getTranslations("clients");
  const { tenant } = await getTenantFor("clients.read");
  if (!tenant.modules.includes("client_app")) redirect("/upgrade/client_app");
  const link = `${await siteOrigin()}/join/${tenant.join_code}`;
  const qr = await QRCode.toString(link, { type: "svg", margin: 1, errorCorrectionLevel: "M" });

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/clients" label={term("back")} />
      <PageHeader title={t("inviteToApp")} description={t("staffHint")} />

      <section className="flex flex-col items-center gap-5 card p-8 text-center">
        <p className="text-xl font-semibold">{tenant.name}</p>
        <div
          role="img"
          aria-label={t("qrLabel")}
          className="size-56 rounded-xl bg-white p-3 [&_svg]:size-full"
          dangerouslySetInnerHTML={{ __html: qr }}
        />
        <div className="flex flex-col gap-1">
          <p className="text-sm text-muted">{t("codeLabel")}</p>
          <p dir="ltr" className="font-mono text-4xl font-bold tracking-[0.3em]">
            {tenant.join_code}
          </p>
        </div>
        <ol className="flex max-w-md list-decimal flex-col gap-1 ps-5 text-start text-sm">
          <li>{t("step1")}</li>
          <li>{t("step2")}</li>
          <li>{t("step3")}</li>
        </ol>
        <p dir="ltr" className="break-all text-xs text-muted">
          {link}
        </p>
      </section>
    </Container>
  );
}
