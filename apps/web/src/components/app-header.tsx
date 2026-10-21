import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";

export async function AppHeader({ children }: { children?: React.ReactNode }) {
  const t = await getTranslations("app");
  return (
    <header
      className={`sticky top-0 z-30 flex print:hidden flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border/70 px-4 py-3 sm:px-6 md:h-16 md:py-0 ${
        // Signed in: the top bar is a plain surface with a hairline, like the side menu (Calm).
        children ? "bg-surface" : "bg-background/75 backdrop-blur-xl"
      }`}
    >
      <Link href="/" className="group flex items-center gap-2 py-1 text-lg font-bold max-md:min-h-11">
        <BrandMark className="size-8 transition-transform duration-300 group-hover:rotate-12" />
        {t("name")}
      </Link>
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-3">
        {children}
        {/* Signed in, language and theme live in the person's settings; public pages keep them here. */}
        {!children && (
          <>
            <LocaleSwitcher />
            <ThemeSwitcher />
          </>
        )}
      </div>
    </header>
  );
}
