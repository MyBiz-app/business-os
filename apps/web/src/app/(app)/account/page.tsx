import { KeyRound } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { avatarSrc } from "@/components/avatar";
import { PalettePicker } from "@/components/palette";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { getActiveMembership } from "@/lib/tenant";

import { savePalette } from "./actions";
import { PictureForm, ProfileForm } from "./profile-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("account");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The signed-in person's own profile, whatever their role. */
export default async function AccountPage() {
  const t = await getTranslations();
  const { me } = await getActiveMembership();
  const name = me.full_name || me.email;

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("account.title")}</h1>
        <p className="text-muted">{t("account.subtitle")}</p>
      </div>
      <section aria-labelledby="profile-heading" className="card flex flex-col gap-6 p-6">
        <h2 id="profile-heading" className="sr-only">
          {t("account.title")}
        </h2>
        <PictureForm id={me.id} name={name} src={avatarSrc(me.id, me.avatar_url)} />
        <div className="border-t border-border" />
        <ProfileForm name={me.full_name} email={me.email} phone={me.phone ?? null} />
      </section>
      <section id="appearance" aria-labelledby="appearance-heading" className="card flex scroll-mt-24 flex-col gap-5 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 id="appearance-heading" className="font-semibold">
              {t("appearance.title")}
            </h2>
            <p className="text-sm text-muted">{t("appearance.subtitle")}</p>
          </div>
          <ThemeSwitcher />
        </div>
        <PalettePicker current={me.palette ?? null} currentColors={me.palette_colors ?? null} save={savePalette} />
      </section>
      <section aria-labelledby="password-heading" className="card flex flex-wrap items-center justify-between gap-3 p-6">
        <h2 id="password-heading" className="flex items-center gap-2 font-semibold">
          <KeyRound aria-hidden="true" className="size-5 text-primary" />
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
    </main>
  );
}
