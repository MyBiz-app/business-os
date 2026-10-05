import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { signOut } from "@/app/(auth)/actions";
import { AppHeader } from "@/components/app-header";
import { getActiveMembership } from "@/lib/tenant";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const t = await getTranslations();
  const { me } = await getActiveMembership();

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader>
        {me.platform_admin && (
          <Link href="/platform" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
            {t("platform.title")}
          </Link>
        )}
        <Link href="/account" className="text-sm font-medium text-muted underline-offset-4 hover:text-foreground hover:underline">
          {me.full_name || t("account.link")}
        </Link>
        <form action={signOut}>
          <button type="submit" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("auth.signOut")}
          </button>
        </form>
      </AppHeader>
      {children}
    </div>
  );
}
