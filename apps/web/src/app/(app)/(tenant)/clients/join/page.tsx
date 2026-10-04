import { getTranslations } from "next-intl/server";
import Link from "next/link";
import QRCode from "qrcode";

import { siteOrigin } from "@/lib/origin";
import { getTenantFor } from "@/lib/tenant";

/** The business's join code and QR code, to print for the front desk or share. */
export default async function JoinCodePage() {
  const t = await getTranslations("join");
  const term = await getTranslations("clients");
  const { tenant } = await getTenantFor("clients.read");
  const link = `${await siteOrigin()}/join/${tenant.join_code}`;
  const qr = await QRCode.toString(link, { type: "svg", margin: 1, errorCorrectionLevel: "M" });

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/clients" className="text-sm text-primary underline-offset-4 hover:underline print:hidden">
        {term("back")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("inviteToApp")}</h1>
        <p className="text-muted">{t("staffHint")}</p>
      </div>

      <section className="flex flex-col items-center gap-5 rounded-2xl border border-border bg-surface p-8 text-center">
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
    </main>
  );
}
