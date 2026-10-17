import { KeyRound } from "lucide-react";
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
import { SecuritySettings } from "./security-settings";
import { NotificationsForm, PictureForm, ProfileForm } from "./profile-form";
import { Container } from "@/components/layout/container";
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

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("account.title")} description={t("account.subtitle")} />
      <section aria-labelledby="profile-heading" className="card flex flex-col gap-6 p-6">
        <h2 id="profile-heading" className="sr-only">
          {t("account.title")}
        </h2>
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
      </section>
      {phoneCodes && (
        <section id="phone-login" aria-labelledby="phone-login-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
          <div className="flex flex-col gap-1">
            <h2 id="phone-login-heading" className="font-semibold">
              {t("account.phoneLogin.title")}
            </h2>
            <p className="text-sm text-muted">{t("account.phoneLogin.hint")}</p>
          </div>
          <PhoneLogin verifiedPhone={auth?.user?.phone_confirmed_at ? (auth.user.phone ?? null) : null} />
        </section>
      )}
      <section id="notifications" aria-labelledby="notifications-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
        <h2 id="notifications-heading" className="font-semibold">
          {t("account.notificationsTitle")}
        </h2>
        <NotificationsForm emailRoster={me.email_roster ?? true} />
      </section>
      <section id="accessibility" aria-labelledby="accessibility-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
        <div className="flex flex-col gap-1">
          <h2 id="accessibility-heading" className="font-semibold">
            {t("accessibility.title")}
          </h2>
          <p className="text-sm text-muted">{t("accessibility.subtitle")}</p>
        </div>
        <AccessibilitySettings />
      </section>
      <section id="appearance" aria-labelledby="appearance-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
        <div className="flex flex-col gap-1">
          <h2 id="appearance-heading" className="font-semibold">
            {t("appearance.title")}
          </h2>
          <p className="text-sm text-muted">{t("appearance.subtitle")}</p>
        </div>
        <PalettePicker current={me.palette ?? null} currentColors={me.palette_colors ?? null} save={savePalette} />
      </section>
      <section id="security" aria-labelledby="security-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
        <div className="flex flex-col gap-1">
          <h2 id="security-heading" className="font-semibold">
            {t("security.title")}
          </h2>
          <p className="text-sm text-muted">{t("security.subtitle")}</p>
        </div>
        <SecuritySettings
          factors={(factorList?.totp ?? []).map((f) => ({ id: f.id, createdAt: f.created_at }))}
          devices={(devices ?? []).map((d) => ({ id: d.id, label: d.label, lastSeenAt: d.last_seen_at, current: d.current }))}
          required={mfa === "required" ? (me.platform_admin ? "team" : "business") : null}
        />
      </section>
      <section aria-labelledby="password-heading" className="card flex flex-wrap items-center justify-between gap-3 p-6">
        <h2 id="password-heading" className="flex items-center gap-2 font-semibold">
          <KeyRound aria-hidden="true" className="size-5 text-primary-ink" />
          {t("account.password")}
        </h2>
        <Link href="/reset-password" className="btn-secondary px-4 py-2 text-sm">
          {t("account.changePassword")}
        </Link>
      </section>
      {me.memberships.length > 0 && (
        <section aria-labelledby="businesses-heading" className="card flex flex-col gap-3 p-6">
          <h2 id="businesses-heading" className="font-semibold">
            {t("account.businesses")}
          </h2>
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
        </section>
      )}
    </Container>
  );
}
