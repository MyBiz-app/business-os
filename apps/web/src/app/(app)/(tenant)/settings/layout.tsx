import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { Container } from "@/components/layout/container";
import { canManageSettings } from "@/lib/permissions";
import { isSolo, visibleTopics } from "@/lib/solo";
import { getTenant } from "@/lib/tenant";

import { SettingsRoom } from "./settings-room";
import { topicsFor } from "./topics";

/** The settings "room" (R13): one frame with a menu of topics. Moving between topics keeps the
 * title and the menu in place; each topic is its own page. */
export default async function SettingsLayout({ children }: LayoutProps<"/settings">) {
  const t = await getTranslations("settings");
  const { tenant } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const items = visibleTopics(topicsFor(tenant.role), isSolo(tenant)).map(({ key, href, group }) => ({ key, href, group }));

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10 print:max-w-none print:py-0">
      <SettingsRoom items={items} title={t("title")} description={t("subtitle")}>
        {children}
      </SettingsRoom>
    </Container>
  );
}
