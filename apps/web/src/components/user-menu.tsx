"use client";

import { LogOut, Settings2, ShieldCheck, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useId, useRef, useState } from "react";

import { Avatar } from "@/components/avatar";
import { moveFocus, useDismiss } from "@/components/use-dismiss";

type Props = {
  id: string;
  name: string;
  email: string;
  avatar: string | null;
  platform: boolean;
  signOut: () => Promise<void>;
};

/** The signed-in person: their picture opens their profile, the MyBiz console (for the team)
 * and signing out. */
export function UserMenu({ id, name, email, avatar, platform, signOut }: Props) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);

  const item = "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors hover:bg-foreground/5 focus-visible:bg-foreground/5";
  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
            requestAnimationFrame(() => document.getElementById(menuId)?.querySelector<HTMLElement>("[role=menuitem]")?.focus());
          }
        }}
        className="flex items-center gap-2 rounded-full p-0.5 pe-2 transition-colors hover:bg-foreground/5 aria-expanded:bg-foreground/5"
      >
        <Avatar id={id} name={name} src={avatar} size="sm" />
        <span dir="auto" className="hidden max-w-36 truncate text-sm font-medium sm:inline">
          {name}
        </span>
        <span className="sr-only">{t("userMenu.open")}</span>
      </button>
      <div
        id={menuId}
        role="menu"
        aria-label={t("userMenu.label")}
        onKeyDown={(event) => moveFocus(event)}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) close();
        }}
        data-open={open}
        className="popover absolute end-0 top-full z-40 mt-2 w-64 origin-top-right rtl:origin-top-left"
      >
        <div className="flex items-center gap-3 border-b border-border px-3 pb-3 pt-2">
          <Avatar id={id} name={name} src={avatar} size="md" />
          <span className="flex min-w-0 flex-col">
            <span dir="auto" className="truncate text-sm font-semibold">
              {name}
            </span>
            <span dir="ltr" className="truncate text-xs text-muted">
              {email}
            </span>
          </span>
        </div>
        <div className="flex flex-col gap-0.5 p-1.5">
          <Link role="menuitem" href="/account" className={item}>
            <UserRound aria-hidden="true" className="size-4 text-muted" />
            {t("account.link")}
          </Link>
          <Link role="menuitem" href="/account#appearance" className={item}>
            <Settings2 aria-hidden="true" className="size-4 text-muted" />
            {t("userMenu.appearance")}
          </Link>
          {platform && (
            <Link role="menuitem" href="/platform" className={item}>
              <ShieldCheck aria-hidden="true" className="size-4 text-muted" />
              {t("platform.title")}
            </Link>
          )}
        </div>
        <form action={signOut} className="border-t border-border p-1.5">
          <button role="menuitem" type="submit" className={`${item} w-full text-danger`}>
            <LogOut aria-hidden="true" className="size-4" />
            {t("auth.signOut")}
          </button>
        </form>
      </div>
    </div>
  );
}
