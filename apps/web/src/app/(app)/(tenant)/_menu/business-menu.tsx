import { Check, ChevronsUpDown, LayoutGrid, Plus } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Image from "next/image";
import Link from "next/link";

import { switchBusiness } from "./actions";

type Props = {
  name: string;
  logo: string | null;
  current: string;
  memberships: { tenant_id: string; tenant_name: string }[];
  /** The current branch's name, when the business has several. */
  branchName: string | null;
};

/** The business at the top of the side menu: opens a list of the person's businesses to switch
 * between, "my businesses" and "add a business". */
export async function BusinessMenu({ name, logo, current, memberships, branchName }: Props) {
  const t = await getTranslations("businessMenu");
  return (
    <details className="group relative mx-3 my-3">
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-background/70 [&::-webkit-details-marker]:hidden">
        {logo ? (
          <Image src={logo} alt="" width={36} height={36} unoptimized className="size-10 rounded-xl object-contain shadow-sm" />
        ) : (
          <span aria-hidden="true" className="btn-primary size-10 shrink-0 text-lg">
            {name.slice(0, 1)}
          </span>
        )}
        <span className="flex min-w-0 flex-1 flex-col">
          <span dir="auto" className="truncate font-semibold">
            {name}
          </span>
          {branchName !== null && (
            <span dir="auto" className="truncate text-xs text-muted">
              {branchName}
            </span>
          )}
        </span>
        <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-muted" />
        <span className="sr-only">{t("switch")}</span>
      </summary>
      <div className="enter absolute inset-x-0 top-full z-30 mt-1 flex flex-col gap-1 rounded-2xl bg-surface p-2 shadow-xl ring-1 ring-border">
        <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{t("myBusinesses")}</p>
        <ul className="flex flex-col">
          {memberships.map((m) => (
            <li key={m.tenant_id}>
              <form action={switchBusiness}>
                <input type="hidden" name="tenant_id" value={m.tenant_id} />
                <button
                  type="submit"
                  aria-current={m.tenant_id === current ? "true" : undefined}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-start text-sm hover:bg-background"
                >
                  <span dir="auto" className="flex-1 truncate">
                    {m.tenant_name}
                  </span>
                  {m.tenant_id === current && <Check aria-hidden="true" className="size-4 text-primary" />}
                </button>
              </form>
            </li>
          ))}
        </ul>
        <div className="my-1 border-t border-border" />
        <Link href="/businesses" className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-background">
          <LayoutGrid aria-hidden="true" className="size-4 text-muted" />
          {t("allBusinesses")}
        </Link>
        <Link href="/onboarding" className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-primary hover:bg-background">
          <Plus aria-hidden="true" className="size-4" />
          {t("newBusiness")}
        </Link>
      </div>
    </details>
  );
}
