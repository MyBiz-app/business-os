import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { cookies } from "next/headers";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { avatarSrc } from "@/components/avatar";
import { PalettePicker } from "@/components/palette";
import { AccessibilitySettings } from "@/components/accessibility";
import { getApi } from "@/lib/api";
import { codeChannels } from "@/lib/auth-providers";
import { DEVICE_COOKIE } from "@/lib/mfa";
import { createClient } from "@/lib/supabase/server";
import { getActiveMembership } from "@/lib/tenant";

import { savePalette } from "./actions";
import { PhoneLogin } from "./phone-login";
import { AccountMenu } from "./account-menu";
import { SecuritySettings } from "./security-settings";
import { NotificationsForm, PictureForm, ProfileForm } from "./profile-form";
import { Container } from "@/components/layout/container";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { PageHeader } from "@/components/layout/page-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("account");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The signed-in person's own profile, whatever their role. */
export default async function AccountPage({ searchParams }: PageProps<"/account">) {
  const t = await getTranslations();
  const { me } = await getActiveMembership();
  const name = me.full_name || me.email;
  // A phone code needs an SMS provider on the project; until then the section stays hidden.
  const phoneCodes = (await codeChannels()).includes("sms");
  const { mfa } = await searchParams;
  const supabase = await createClient();
  const { data: factorList } = await supabase.auth.mfa.listFactors();
  const deviceId = (await cookies()).get(DEVICE_COOKIE)?.value;
  const api = await getApi();
  const { data: devices } = await api.GET("/me/devices", { headers: deviceId ? { "X-Device-Id": deviceId } : {} });
  const { data: auth } = phoneCodes ? await (await createClient()).auth.getUser() : { data: null };

  const menu = [
    { id: "profile", label: t("account.detailsTitle") },
    ...(phoneCodes ? [{ id: "phone-login", label: t("account.phoneLogin.title") }] : []),
    { id: "notifications", label: t("account.notificationsTitle") },
    { id: "accessibility", label: t("accessibility.title") },
    { id: "appearance", label: t("appearance.title") },
    { id: "security", label: t("security.title") },
    { id: "password", label: t("account.password") },
    ...(me.memberships.length > 0 ? [{ id: "businesses", label: t("account.businesses") }] : []),
  ];
  const key = (id: string) => `account:${id}`;

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("account.title")} description={t("account.subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start xl:gap-10">
        <AccountMenu items={menu} />
        <div className="flex min-w-0 flex-col gap-4">
          <CollapsibleSection id="profile" storageKey={key("profile")} defaultOpen title={t("account.detailsTitle")}>
            <div className="flex flex-col gap-6">
              <PictureForm id={me.id} name={name} src={avatarSrc(me.id, me.avatar_url)} />
              <div className="border-t border-border" />
              <ProfileForm
                name={me.full_name}
                email={me.email}
                phone={me.phone ?? null}
                birthDate={me.birth_date ?? null}
                addressLine={me.address_line ?? null}
                city={me.city ?? null}
                postalCode={me.postal_code ?? null}
              />
            </div>
          </CollapsibleSection>
          {phoneCodes && (
            <CollapsibleSection id="phone-login" storageKey={key("phone-login")} title={t("account.phoneLogin.title")} description={t("account.phoneLogin.hint")}>
              <PhoneLogin verifiedPhone={auth?.user?.phone_confirmed_at ? (auth.user.phone ?? null) : null} />
            </CollapsibleSection>
          )}
          <CollapsibleSection id="notifications" storageKey={key("notifications")} title={t("account.notificationsTitle")}>
            <NotificationsForm emailRoster={me.email_roster ?? true} />
          </CollapsibleSection>
          <CollapsibleSection id="accessibility" storageKey={key("accessibility")} title={t("accessibility.title")} description={t("accessibility.subtitle")}>
            <AccessibilitySettings />
          </CollapsibleSection>
          <CollapsibleSection id="appearance" storageKey={key("appearance")} title={t("appearance.title")} description={t("appearance.subtitle")}>
            <PalettePicker current={me.palette ?? null} currentColors={me.palette_colors ?? null} save={savePalette} />
          </CollapsibleSection>
          <CollapsibleSection id="security" storageKey={key("security")} title={t("security.title")} description={t("security.subtitle")}>
            <SecuritySettings
              factors={(factorList?.totp ?? []).map((f) => ({ id: f.id, createdAt: f.created_at }))}
              devices={(devices ?? []).map((d) => ({ id: d.id, label: d.label, lastSeenAt: d.last_seen_at, current: d.current }))}
              required={mfa === "required" ? (me.platform_admin ? "team" : "business") : null}
            />
          </CollapsibleSection>
          <CollapsibleSection id="password" storageKey={key("password")} title={t("account.password")}>
            <Link href="/reset-password" className="btn-secondary inline-flex px-4 py-2 text-sm">
              {t("account.changePassword")}
            </Link>
          </CollapsibleSection>
          {me.memberships.length > 0 && (
            <CollapsibleSection id="businesses" storageKey={key("businesses")} title={t("account.businesses")}>
              <ul className="flex flex-col divide-y divide-border">
                {me.memberships.map((m) => (
                  <li key={m.tenant_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span dir="auto" className="font-medium">
                      {m.tenant_name}
                    </span>
                    <span className="text-muted">{t(`roles.${m.role}`)}</span>
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}
        </div>
      </div>
    </Container>
  );
}
