import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Image from "next/image";
import { notFound } from "next/navigation";

import { AppHeader } from "@/components/app-header";
import { apiAssetUrl, getApi } from "@/lib/api";
import { brandStyle } from "@/lib/brand";

import { InquiryForm } from "./inquiry-form";

async function business(code: string) {
  const { data } = await (await getApi()).GET("/public/businesses/{code}", { params: { path: { code } } });
  return data;
}

export async function generateMetadata({ params }: PageProps<"/inquiry/[code]">): Promise<Metadata> {
  const found = await business((await params).code);
  const t = await getTranslations("inquiry");
  return { title: found ? t("title", { name: found.name }) : t("closed") };
}

/** A business's public "leave your details" page; inquiries arrive as new leads (CRM). */
export default async function InquiryPage({ params }: PageProps<"/inquiry/[code]">) {
  const { code } = await params;
  const t = await getTranslations("inquiry");
  const found = await business(code);
  if (!found) notFound();
  const logo = apiAssetUrl(found.logo_url);

  return (
    <div className="brand flex flex-1 flex-col" style={brandStyle(found.primary_color)}>
      <AppHeader />
      <main className="enter mx-auto flex w-full max-w-lg flex-1 flex-col items-center gap-6 px-6 py-12">
        {logo ? (
          <Image src={logo} alt="" width={80} height={80} unoptimized className="size-20 rounded-2xl border border-border object-contain" />
        ) : (
          <span aria-hidden="true" className="btn-primary size-20 text-3xl">
            {found.name.slice(0, 1)}
          </span>
        )}
        <div className="flex flex-col gap-2 text-center">
          <h1 dir="auto" className="text-3xl font-bold">{found.name}</h1>
          <p className="text-muted">{found.inquiries ? t("subtitle") : t("closed")}</p>
        </div>
        {found.inquiries && (
          <section className="card w-full p-6">
            <InquiryForm code={code} />
          </section>
        )}
      </main>
    </div>
  );
}
