import { Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";

export async function AppHeader({ children }: { children?: React.ReactNode }) {
  const t = await getTranslations("app");
  return (
    <header className="sticky top-0 z-30 flex print:hidden flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border/70 bg-background/75 px-4 py-3 sm:px-6 backdrop-blur-xl md:h-16 md:py-0">
      <Link href="/" className="group flex items-center gap-2 text-lg font-bold">
        <span
          aria-hidden="true"
          className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand-from to-brand-to text-white shadow-md transition-transform duration-300 group-hover:rotate-12"
        >
          <Sparkles className="size-4" />
        </span>
        {t("name")}
      </Link>
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-3">
        {children}
        <LocaleSwitcher />
        <ThemeSwitcher />
      </div>
    </header>
  );
}
