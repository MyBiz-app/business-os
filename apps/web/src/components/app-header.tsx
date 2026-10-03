import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeSwitcher } from "@/components/theme-switcher";

export async function AppHeader({ children }: { children?: React.ReactNode }) {
  const t = await getTranslations("app");
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-4">
      <Link href="/" className="text-lg font-bold">
        {t("name")}
      </Link>
      <div className="flex flex-wrap items-center gap-4">
        {children}
        <LocaleSwitcher />
        <ThemeSwitcher />
      </div>
    </header>
  );
}
