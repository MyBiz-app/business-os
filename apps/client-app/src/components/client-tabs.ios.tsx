import { NativeTabs } from "expo-router/native-tabs";
import { useTranslations } from "use-intl";

import { font } from "@business-os/app-kit/lib/typography";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

import { useBusiness } from "@/providers/business-provider";
import { useInbox } from "@/providers/inbox-provider";

/**
 * The client app's five tabs on iOS: the system tab bar (UITabBarController), so it gets the
 * system's own glass, haptics, and the large-title and scroll-edge behavior, with SF Symbols for
 * icons. The tab bar is tinted in the selected business's color, and follows the app's own
 * light/dark choice when that differs from the phone's.
 */
export function ClientTabs() {
  const t = useTranslations("client.tabs");
  const { palette } = useBusiness();
  const { scheme } = useTheme();
  const { inbox } = useInbox();
  const unread = inbox?.unread ?? 0;

  return (
    <NativeTabs
      tintColor={palette.primary}
      iconColor={palette.muted}
      labelStyle={{ color: palette.muted, fontSize: 12, fontFamily: font.medium.fontFamily }}
      blurEffect={scheme === "dark" ? "systemMaterialDark" : "systemMaterialLight"}
      badgeBackgroundColor={palette.primary}
      badgeTextColor={palette.onPrimary}
    >
      <NativeTabs.Trigger name="home">
        <NativeTabs.Trigger.Label>{t("home")}</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "house", selected: "house.fill" }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="schedule">
        <NativeTabs.Trigger.Label>{t("book")}</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "calendar", selected: "calendar" }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="bookings">
        <NativeTabs.Trigger.Label>{t("mine")}</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "ticket", selected: "ticket.fill" }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="updates">
        <NativeTabs.Trigger.Label>{t("updates")}</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "bell", selected: "bell.fill" }} />
        <NativeTabs.Trigger.Badge hidden={unread === 0}>{unread > 9 ? "9+" : String(unread)}</NativeTabs.Trigger.Badge>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="profile">
        <NativeTabs.Trigger.Label>{t("profile")}</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "person", selected: "person.fill" }} />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
