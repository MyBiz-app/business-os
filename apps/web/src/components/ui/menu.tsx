"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { moveFocus } from "@/components/use-dismiss";
import type { Placement } from "@/lib/popover-position";

import { cx } from "./cx";
import { Popover, type PopoverTriggerProps } from "./popover";

export type MenuItem =
  | {
      key: string;
      label: ReactNode;
      /** A 16px icon (aria-hidden). */
      icon?: ReactNode;
      /** A link item goes to a page; without it the item runs `onSelect`. */
      href?: string;
      onSelect?: () => void;
      /** danger: delete, remove, sign out. */
      tone?: "default" | "danger";
      disabled?: boolean;
    }
  | { key: string; separator: true };

const ITEM =
  "btn-plain flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-start text-sm outline-none transition-colors hover:bg-subtle focus-visible:bg-subtle disabled:opacity-50 min-h-9";

/** A list of actions that opens under its trigger: the arrow keys move between the items, Enter
 * runs one, Esc and Tab close it. Built on `Popover`, so it is positioned and dismissed the same
 * way as every other floating panel. */
export function Menu({
  label,
  trigger,
  items,
  placement = "bottom-end",
  className,
}: {
  /** The menu's name for screen readers. */
  label: string;
  trigger: (props: PopoverTriggerProps) => ReactNode;
  items: MenuItem[];
  placement?: Placement;
  /** Width of the panel; defaults to `w-56`. */
  className?: string;
}) {
  return (
    <Popover
      trigger={trigger}
      label={label}
      role="menu"
      placement={placement}
      className={cx("w-56 p-1.5", className)}
      onKeyDown={(event) => moveFocus(event, "[role=menuitem]:not([disabled])")}
    >
      {({ close }) => (
        <div className="flex flex-col gap-0.5" onKeyDown={(event) => event.key === "Tab" && close()}>
          {items.map((item) => {
            if ("separator" in item) return <div key={item.key} role="separator" className="my-1 h-px bg-border" />;
            const className = cx(ITEM, item.tone === "danger" && "text-danger");
            const content = (
              <>
                {item.icon}
                {item.label}
              </>
            );
            if (item.href && !item.disabled) {
              return (
                <Link key={item.key} role="menuitem" tabIndex={-1} href={item.href} onClick={close} className={className}>
                  {content}
                </Link>
              );
            }
            return (
              <button
                key={item.key}
                type="button"
                role="menuitem"
                tabIndex={-1}
                disabled={item.disabled}
                onClick={() => {
                  close();
                  item.onSelect?.();
                }}
                className={className}
              >
                {content}
              </button>
            );
          })}
        </div>
      )}
    </Popover>
  );
}
