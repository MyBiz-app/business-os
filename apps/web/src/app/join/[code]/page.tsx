import { getTranslations } from "next-intl/server";
import Image from "next/image";
import { notFound } from "next/navigation";

import { AppHeader } from "@/components/app-header";
import { apiAssetUrl, getApi } from "@/lib/api";
import { brandStyle } from "@/lib/brand";

/** Public landing page behind a business's QR code: its branding and how to join in the app. */
export default async function JoinPage({ params }: PageProps<"/join/[code]">) {
  const { code } = await params;
  const t = await getTranslations("join");
  const { data: business } = await (await getApi()).GET("/public/businesses/{code}", {
    params: { path: { code } },
  });
  if (!business) notFound();
  const logo = apiAssetUrl(business.logo_url);
  const joinCode = code.toUpperCase();

  return (
    <div className="brand flex flex-1 flex-col" style={brandStyle(business.primary_color)}>
      <AppHeader />
      <main className="enter mx-auto flex w-full max-w-md flex-1 flex-col items-center gap-6 px-6 py-12 text-center">
        {logo ? (
          <Image src={logo} alt="" width={80} height={80} unoptimized className="size-20 rounded-2xl border border-border object-contain" />
        ) : (
          <span aria-hidden className="size-20 rounded-2xl bg-primary" />
        )}
        <h1 className="text-3xl font-bold">{t("title", { name: business.name })}</h1>
        <p className="text-muted">{t("body")}</p>
        <div className="flex flex-col gap-1">
          <p className="text-sm text-muted">{t("codeLabel")}</p>
          <p dir="ltr" className="font-mono text-4xl font-bold tracking-[0.3em]">
            {joinCode}
          </p>
        </div>
        <ol className="flex list-decimal flex-col gap-1 ps-5 text-start">
          <li>{t("step1")}</li>
          <li>{t("step2")}</li>
          <li>{t("step3")}</li>
        </ol>
        <a
          href={`mybiz://join?code=${encodeURIComponent(joinCode)}`}
          className="w-full btn-primary px-4 py-3"
        >
          {t("openApp")}
        </a>
        {/* The client app also runs in the browser (see apps/mobile/README.md). */}
        {process.env.NEXT_PUBLIC_CLIENT_APP_URL && (
          <a
            href={`${process.env.NEXT_PUBLIC_CLIENT_APP_URL}/join?code=${encodeURIComponent(joinCode)}`}
            className="btn-secondary w-full px-4 py-3"
          >
            {t("openInBrowser")}
          </a>
        )}
      </main>
    </div>
  );
}
