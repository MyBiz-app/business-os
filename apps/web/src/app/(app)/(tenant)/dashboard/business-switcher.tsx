"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { switchBusiness } from "./actions";

type Props = {
  current: string;
  memberships: { tenant_id: string; tenant_name: string }[];
};

export function BusinessSwitcher({ current, memberships }: Props) {
  const t = useTranslations("dashboard");

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      {memberships.length > 1 && (
        <form action={switchBusiness}>
          <label className="flex items-center gap-2">
            <span className="text-muted">{t("switchBusiness")}</span>
            <select
              name="tenant_id"
              defaultValue={current}
              onChange={(event) => event.currentTarget.form?.requestSubmit()}
              className="rounded-md border border-border bg-surface px-2 py-1"
            >
              {memberships.map((m) => (
                <option key={m.tenant_id} value={m.tenant_id}>
                  {m.tenant_name}
                </option>
              ))}
            </select>
          </label>
        </form>
      )}
      <Link href="/onboarding" className="text-primary underline-offset-4 hover:underline">
        {t("newBusiness")}
      </Link>
    </div>
  );
}
