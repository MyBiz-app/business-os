import { getTranslations } from "next-intl/server";

import { signOut } from "@/app/(auth)/actions";
import { AppHeader } from "@/components/app-header";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const t = await getTranslations("auth");

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader>
        <form action={signOut}>
          <button type="submit" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("signOut")}
          </button>
        </form>
      </AppHeader>
      {children}
    </div>
  );
}
