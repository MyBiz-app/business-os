"use client";

// The plan so far in the sign-up journey: the cart, the summary lines and the add-ons rail.

import { Check, ChevronUp, ShoppingBag, X } from "lucide-react";

import { ModuleIcon } from "@/components/modules/module-icon";
import { type ModuleKey, OFFERS, type Offer, type PriceLine } from "@/lib/signup-plan";

import { OFFER_ICON, type T } from "./journey-pieces";

export function SummaryLines({
  lines,
  label,
  money,
  onRemove,
  removeLabel,
}: {
  lines: PriceLine[];
  label: (key: PriceLine["key"]) => string;
  money: (amount: number) => string;
  onRemove: (key: ModuleKey) => void;
  removeLabel: string;
}) {
  return (
    <ul className="flex flex-col divide-y divide-border">
      {lines.map((line) => (
        <li key={line.key} className="flex items-center justify-between gap-3 py-3">
          <span className="flex items-center gap-2">
            {label(line.key)}
            {line.quantity > 1 && <span className="text-sm text-muted" dir="ltr">× {line.quantity}</span>}
          </span>
          <span className="flex items-center gap-2">
            <bdi className="font-semibold">{money(line.amount)}</bdi>
            {line.key !== "core" && line.key !== "extra_location" && (
              <button
                type="button"
                onClick={() => onRemove(line.key as ModuleKey)}
                aria-label={`${removeLabel}: ${label(line.key)}`}
                className="flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The add-ons at a glance: where the person is, what they added, and a way to jump back. */
export function AddOnRail({
  current,
  added,
  onPick,
  label,
  addedLabel,
  navLabel,
}: {
  current: Offer;
  added: (offer: Offer) => boolean;
  onPick: (offer: Offer) => void;
  label: (offer: Offer) => string;
  addedLabel: string;
  navLabel: string;
}) {
  return (
    <nav aria-label={navLabel} className="relative -mx-1 overflow-x-auto px-1 pb-1">
      <ol className="flex min-w-max gap-2">
        {OFFERS.map((offer) => {
          const isCurrent = offer === current;
          return (
            <li key={offer}>
              <button
                type="button"
                onClick={() => onPick(offer)}
                aria-current={isCurrent ? "step" : undefined}
                className={`flex items-center gap-2 rounded-full border py-1.5 ps-1.5 pe-3 text-sm font-semibold transition-colors ${
                  isCurrent ? "border-primary bg-primary/10 text-primary" : "border-border bg-surface hover:border-primary/50"
                }`}
              >
                <ModuleIcon module={OFFER_ICON[offer]} size="sm" />
                {label(offer)}
                {added(offer) && (
                  <span className="flex size-5 items-center justify-center rounded-full bg-success text-white">
                    <Check aria-hidden="true" className="size-3" />
                    <span className="sr-only">{addedLabel}</span>
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export type CartLine = PriceLine & { label: string };

/** The plan so far: a card beside the steps on wide screens, a bar at the bottom on phones. */
export function Cart({
  lines,
  once,
  total,
  onceTotal,
  money,
  open,
  onToggle,
  onRemove,
  t,
}: {
  lines: CartLine[];
  once: CartLine[];
  total: number;
  onceTotal: number;
  money: (amount: number) => string;
  open: boolean;
  onToggle: () => void;
  onRemove: (key: ModuleKey) => void;
  t: T;
}) {
  const list = (items: CartLine[]) => (
    <ul className="flex flex-col gap-2">
      {items.map((line) => (
        <li key={line.key} className="group flex animate-[pop_360ms_var(--ease-out)_both] items-center justify-between gap-3 text-sm">
          <span className="flex min-w-0 items-center gap-2">
            {line.key === "core" ? (
              <span aria-hidden="true" className="icon-tile size-8">
                <Check className="size-4" />
              </span>
            ) : (
              <ModuleIcon module={line.key} size="sm" />
            )}
            <span className="truncate">{line.label}</span>
            {line.quantity > 1 && <span className="text-muted" dir="ltr">× {line.quantity}</span>}
          </span>
          <span className="flex items-center gap-1">
            <bdi className="font-semibold">{money(line.amount)}</bdi>
            {line.key !== "core" && line.key !== "extra_location" && (
              <button
                type="button"
                onClick={() => onRemove(line.key as ModuleKey)}
                aria-label={`${t("offer.remove")}: ${line.label}`}
                className="flex size-7 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
  const onceBlock = once.length > 0 && (
    <div className="flex flex-col gap-2 border-t border-dashed border-border pt-3">
      <p className="flex items-baseline justify-between gap-2 text-xs font-semibold text-muted">
        <span>{t("cart.once")}</span>
        <bdi>{money(onceTotal)}</bdi>
      </p>
      {list(once)}
    </div>
  );
  const totals = (
    <div className="flex flex-col gap-1 border-t border-border pt-3">
      <p className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{t("cart.monthly")}</span>
        <span key={total} className="animate-[pop_360ms_var(--ease-out)_both] text-xl font-extrabold">
          <bdi>{money(total)}</bdi>
        </span>
      </p>
      <p className="flex items-baseline justify-between gap-2 text-success">
        <span className="text-sm font-semibold">{t("cart.today")}</span>
        <span className="font-bold">{t("cart.free")}</span>
      </p>
    </div>
  );

  return (
    <>
      <aside aria-label={t("cart.title")} className="hidden lg:block">
        <div className="card sticky top-24 flex flex-col gap-4 p-5">
          <h2 className="flex items-center gap-2 font-bold">
            <ShoppingBag aria-hidden="true" className="size-5 text-primary" />
            {t("cart.title")}
          </h2>
          {list(lines)}
          {lines.length === 1 && once.length === 0 && <p className="text-sm text-muted">{t("cart.emptyHint")}</p>}
          {onceBlock}
          {totals}
          <p className="rounded-xl bg-primary/10 px-3 py-2 text-center text-sm font-semibold text-primary">{t("cart.trial")}</p>
        </div>
      </aside>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 shadow-[0_-8px_24px_-12px_rgb(0_0_0/0.25)] backdrop-blur lg:hidden">
        {open && (
          <div id="cart-sheet" className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto border-b border-border px-4 py-4">
            {list(lines)}
            {onceBlock}
            <p className="text-center text-sm font-semibold text-primary">{t("cart.trial")}</p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls="cart-sheet"
          className="flex w-full items-center justify-between gap-3 px-4 py-3"
        >
          <span className="flex items-center gap-2 text-sm font-semibold">
            <ShoppingBag aria-hidden="true" className="size-5 text-primary" />
            {open ? t("cart.hide") : t("cart.show")}
            <span className="text-muted">· {t("cart.items", { count: lines.length + once.length })}</span>
          </span>
          <span className="flex items-center gap-2">
            <span key={total} className="animate-[pop_360ms_var(--ease-out)_both] text-lg font-extrabold">
              <bdi>{money(total)}</bdi>
            </span>
            <ChevronUp aria-hidden="true" className={`size-5 transition-transform ${open ? "" : "rotate-180"}`} />
          </span>
        </button>
      </div>
    </>
  );
}
