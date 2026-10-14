import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { AccessibilityWidget } from "@/components/accessibility-widget";
import { AuthScene } from "@/components/auth/auth-scene";
import { FitToScreen } from "@/components/auth/fit-to-screen";
import { BrandMark } from "@/components/brand-mark";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeToggle } from "@/components/theme-toggle";

/** The sign-in frame: a navy brand panel beside the form on wide screens, the form alone on a
 * phone. The language and light/dark controls sit on the form side so they work in both. */
export async function AuthShell({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("auth.panel");
  const tApp = await getTranslations("app");
  return (
    <>
    <div className="flex h-dvh flex-col lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:grid-rows-[minmax(0,1fr)]">
      <aside className="relative isolate hidden min-h-0 flex-col justify-between gap-6 overflow-hidden bg-navy p-8 text-white lg:flex xl:p-12">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 -start-24 -z-10 size-[28rem] rounded-full bg-primary/40 blur-[110px]" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -end-16 -z-10 size-[26rem] rounded-full bg-electric/25 blur-[110px]" />
        <Link href="/" className="flex w-fit items-center gap-2 text-xl font-bold">
          <BrandMark className="size-9" />
          {tApp("name")}
        </Link>
        <div className="flex min-h-0 flex-1 flex-col justify-center gap-5 xl:gap-6">
          <p className="w-fit rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm font-medium text-white/85">{t("eyebrow")}</p>
          <h2 className="text-3xl font-extrabold leading-tight tracking-tight xl:text-5xl [@media(max-height:760px)]:xl:text-4xl">{t("title")}</h2>
          <ul className="flex flex-col gap-3 text-base text-white/80 xl:text-lg [@media(max-height:620px)]:hidden">
            {(t.raw("points") as string[]).map((point) => (
              <li key={point} className="flex items-start gap-3">
                <Check aria-hidden="true" className="mt-1 size-5 shrink-0 text-electric" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <AuthScene />
      </aside>
      <div className="flex min-h-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-3 px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold lg:hidden">
            <BrandMark className="size-8" />
            {tApp("name")}
          </Link>
          <Link href="/" className="group hidden items-center gap-1 text-sm font-semibold text-muted hover:text-foreground lg:inline-flex">
            <ArrowLeft aria-hidden="true" className="size-4 transition-transform group-hover:-translate-x-1 rtl:hidden" />
            <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1 ltr:hidden" />
            {t("back")}
          </Link>
          <div className="flex items-center gap-2">
            <LocaleSwitcher />
            <ThemeToggle />
          </div>
        </header>
        <FitToScreen>
          <div className="card flex w-full flex-col gap-5 p-6 shadow-xl sm:p-8 [@media(min-height:860px)]:sm:p-9">{children}</div>
        </FitToScreen>
      </div>
    </div>
    <AccessibilityWidget />
    </>
  );
}

/** A page title with an optional one-line explanation under it. */
export function AuthHeading({ title, subtitle, icon }: { title: string; subtitle?: string; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      {icon && (
        <span aria-hidden="true" className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          {icon}
        </span>
      )}
      <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
      {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
    </div>
  );
}
