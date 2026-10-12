import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AccessibilityWidget } from "@/components/accessibility-widget";
import { BrandMark } from "@/components/brand-mark";
import { ScopedMessages } from "@/components/scoped-messages";

/** Sign-in screens: a navy brand panel beside the form on wide screens, the form alone on a phone. */
export default async function AuthLayout({ children }: LayoutProps<"/">) {
  const t = await getTranslations("auth.panel");
  const tApp = await getTranslations("app");
  return (
    <ScopedMessages scopes={["auth"]}>
      <div className="flex flex-1 flex-col lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <aside className="relative isolate hidden flex-col justify-between gap-10 overflow-hidden bg-navy p-12 text-white lg:flex">
          <div aria-hidden="true" className="pointer-events-none absolute -top-24 -start-24 -z-10 size-[28rem] rounded-full bg-primary/40 blur-[110px]" />
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -end-16 -z-10 size-[26rem] rounded-full bg-electric/25 blur-[110px]" />
          <div className="flex items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-2 text-xl font-bold">
              <BrandMark className="size-9" />
              {tApp("name")}
            </Link>
            <Link href="/" className="group inline-flex items-center gap-1 text-sm font-semibold text-white/70 hover:text-white">
              <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 rtl:hidden" />
              <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1 ltr:hidden" />
              {t("back")}
            </Link>
          </div>
          <div className="flex flex-col gap-6">
            <p className="w-fit rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85">{t("eyebrow")}</p>
            <h2 className="text-4xl font-extrabold leading-tight tracking-tight xl:text-5xl">{t("title")}</h2>
            <ul className="flex flex-col gap-3 text-lg text-white/80">
              {(t.raw("points") as string[]).map((point) => (
                <li key={point} className="flex items-start gap-3">
                  <Check aria-hidden="true" className="mt-1 size-5 shrink-0 text-electric" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <div aria-hidden="true" className="h-12" />
        </aside>
        <div className="flex flex-1 flex-col">
          <header className="flex items-center justify-between px-6 py-5 lg:hidden">
            <Link href="/" className="flex items-center gap-2 text-lg font-bold">
              <BrandMark className="size-8" />
              {tApp("name")}
            </Link>
          </header>
          <main className="enter flex flex-1 items-center justify-center px-5 py-10">
            <div className="card flex w-full max-w-md flex-col gap-6 p-7 shadow-xl sm:p-9">{children}</div>
          </main>
        </div>
        <AccessibilityWidget />
      </div>
    </ScopedMessages>
  );
}
