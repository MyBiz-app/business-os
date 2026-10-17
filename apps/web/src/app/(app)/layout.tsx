import { ScopedMessages } from "@/components/scoped-messages";
import { signOut } from "@/app/(auth)/actions";
import { ActivityGuard } from "@/components/activity-guard";
import { DeviceCheck } from "@/components/device-check";
import { LegalBanner } from "@/components/legal-banner";
import { MfaBanner } from "@/components/mfa-banner";
import { AnnouncementsPopup, type PopupItem } from "@/components/announcements-popup";
import { AppHeader } from "@/components/app-header";
import { avatarSrc } from "@/components/avatar";
import { PaletteSync } from "@/components/palette";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";
import { getApi } from "@/lib/api";
import { getActiveMembership } from "@/lib/tenant";

/** The pop-ups meant for this person; a failure here never blocks the page. */
async function popups(): Promise<PopupItem[]> {
  try {
    const { data } = await (await getApi()).GET("/me/announcements");
    return (data ?? []).map((a) => ({
      id: a.id,
      subject: a.texts.subject,
      body: a.texts.body,
      ctaLabel: a.texts.cta_label,
      ctaUrl: a.texts.cta_url,
      imageUrl: a.texts.image_url,
    }));
  } catch {
    return [];
  }
}

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const { me } = await getActiveMembership();
  const announcements = await popups();

  return (
    <ScopedMessages scopes={["app"]}>
    <div className="app-shell flex flex-1 flex-col">
      <PaletteSync palette={me.palette ?? null} colors={me.palette_colors ?? null} />
      <AppHeader>
        <ThemeToggle />
        <UserMenu
          id={me.id}
          name={me.full_name || me.email}
          email={me.email}
          avatar={avatarSrc(me.id, me.avatar_url)}
          platform={me.platform_admin}
          signOut={signOut}
        />
      </AppHeader>
      <LegalBanner pending={me.legal_pending ?? []} />
      <MfaBanner memberships={me.memberships.map((m) => m.role)} platform={me.platform_admin} />
      {children}
      <ActivityGuard />
      <DeviceCheck />
      {announcements.length > 0 && <AnnouncementsPopup items={announcements} />}
    </div>
    </ScopedMessages>
  );
}
