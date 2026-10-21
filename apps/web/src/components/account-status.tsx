"use client";

import { MapPin, ShieldAlert, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { skipAddressReminder, snoozeMfaReminder } from "@/app/(app)/account/security-actions";
import { MfaRiskDialog } from "@/components/mfa-risk-dialog";
import { useToast } from "@/components/toast/toaster";
import { type AccountStatusItem, itemsKey, STATUS_CARD_COOKIE } from "@/lib/account-status";

const ICONS = { mfa: ShieldAlert, mfa_required: ShieldAlert, address: MapPin } as const;
const HREFS = { mfa: "/account#security", mfa_required: "/account#security", address: "/account#profile" } as const;

/** The quiet list of the account status in the menu under the person's picture: one link per item
 * to where it is completed. */
export function AccountStatusLinks({ items, itemClassName }: { items: AccountStatusItem[]; itemClassName: string }) {
  const t = useTranslations("accountStatus");
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-0.5 border-b border-border p-1.5">
      <p className="px-2.5 pb-0.5 pt-1 text-xs font-medium text-muted">{t("menuTitle")}</p>
      {items.map((item) => {
        const Icon = ICONS[item];
        return (
          <Link key={item} role="menuitem" href={HREFS[item]} className={itemClassName}>
            <Icon aria-hidden="true" className="size-4 text-warning" />
            {t(`${item === "mfa_required" ? "mfaRequired" : item}.title`)}
          </Link>
        );
      })}
    </div>
  );
}

/** The home page card: "2 things worth completing", each with its choices. Two-step sign-in: turn
 * it on, "remind me in a week" or "I don't want it" (the warning window, kept as the person's
 * record); the MyBiz team can only turn it on. The home address: fill it in or skip it. Closing the
 * card hides it until a new item comes up; the dot by the picture stays until each is answered. */
export function AccountStatusCard({ items }: { items: AccountStatusItem[] }) {
  const t = useTranslations("accountStatus");
  const router = useRouter();
  const toast = useToast();
  const [closed, setClosed] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [pending, startTransition] = useTransition();
  if (closed || items.length === 0) return null;

  const run = (action: () => Promise<{ ok: boolean }>) =>
    startTransition(async () => {
      if ((await action()).ok) router.refresh();
      else toast("error", t("error"));
    });
  const close = () => {
    document.cookie = `${STATUS_CARD_COOKIE}=${itemsKey(items)}; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax`;
    setClosed(true);
  };
  const link = "btn-primary px-3 py-1.5 text-sm";
  const quiet = "btn-secondary px-3 py-1.5 text-sm";

  return (
    <section aria-labelledby="account-status-title" className="card relative flex flex-col gap-4 p-5" aria-busy={pending}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h2 id="account-status-title" className="font-semibold">
            {t("cardTitle", { count: items.length })}
          </h2>
          <p className="text-sm text-muted">{t("cardHint")}</p>
        </div>
        <button type="button" onClick={close} className="btn-plain -m-1.5 rounded-full p-1.5 text-muted hover:bg-foreground/5">
          <X aria-hidden="true" className="size-4" />
          <span className="sr-only">{t("close")}</span>
        </button>
      </div>
      <ul className="flex flex-col divide-y divide-border">
        {items.map((item) => {
          const Icon = ICONS[item];
          const key = item === "mfa_required" ? "mfaRequired" : item;
          return (
            <li key={item} className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-warning" />
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium">{t(`${key}.title`)}</p>
                  <p className="text-sm text-muted">{t(`${key}.text`)}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 ps-8 sm:ps-0">
                {item === "address" ? (
                  <>
                    <Link href={HREFS.address} className={link}>
                      {t("address.fill")}
                    </Link>
                    <button type="button" className={quiet} disabled={pending} onClick={() => run(skipAddressReminder)}>
                      {t("address.skip")}
                    </button>
                  </>
                ) : (
                  <>
                    <Link href={HREFS[item]} className={link}>
                      {t(item === "mfa" ? "mfa.enable" : "mfaRequired.enable")}
                    </Link>
                    {item === "mfa" && (
                      <>
                        <button type="button" className={quiet} disabled={pending} onClick={() => run(snoozeMfaReminder)}>
                          {t("mfa.snooze")}
                        </button>
                        <button type="button" className="btn-plain px-2 py-1.5 text-sm text-muted underline underline-offset-4" onClick={() => setDeclining(true)}>
                          {t("mfa.decline")}
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {declining && (
        <MfaRiskDialog
          source="opt_out"
          onClose={() => setDeclining(false)}
          onDone={() => {
            setDeclining(false);
            router.refresh();
          }}
        />
      )}
    </section>
  );
}
