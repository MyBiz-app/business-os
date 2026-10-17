"use client";

import { Braces } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

export type VariableName =
  | "first_name" | "last_name" | "full_name" | "phone" | "email" | "birthday" | "id_last4"
  | "plan_name" | "plan_expires" | "sessions_left" | "next_booking" | "next_service" | "staff_name"
  | "business" | "branch" | "branch_address" | "app_link" | "join_code" | "booking_link";
export type GroupName = "client" | "plan" | "booking" | "business";

export type VariableGroup = { key: string; variables: string[] };

/** The button that lists the variables a message may use, by group, with an optional fallback
 * for people who have no value. Picking one hands back the token, e.g. `{plan_name|member}`. */
export function VariablePicker({ groups, onPick }: { groups: VariableGroup[]; onPick: (token: string) => void }) {
  const t = useTranslations("messaging");
  const [open, setOpen] = useState(false);
  const [fallback, setFallback] = useState("");
  const panelId = useId();
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key === "Escape") setOpen(false);
      } else if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const pick = (name: string) => {
    const value = fallback.trim().replace(/[{}|]/g, "");
    onPick(value ? `{${name}|${value}}` : `{${name}}`);
    setOpen(false);
  };

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="btn-plain flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 font-medium text-foreground transition-colors hover:bg-primary/20 focus-visible:ring-2 focus-visible:ring-primary"
      >
        <Braces aria-hidden="true" className="size-3.5" />
        {t("addVariable")}
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={t("addVariable")}
          className="absolute start-0 top-full z-20 mt-2 flex max-h-80 w-72 flex-col gap-3 overflow-y-auto rounded-xl border border-border bg-surface p-3 shadow-xl"
        >
          <label className="flex flex-col gap-1 text-xs font-medium">
            {t("fallbackLabel")}
            <input
              value={fallback}
              onChange={(event) => setFallback(event.target.value)}
              maxLength={40}
              dir="auto"
              placeholder={t("fallbackPlaceholder")}
              className="control px-2 py-1.5 font-normal"
            />
            <span className="font-normal text-muted">{t("fallbackHint")}</span>
          </label>
          {groups.map((group) => (
            <div key={group.key} className="flex flex-col gap-1.5">
              <p className="text-xs font-semibold text-muted">{t(`variableGroups.${group.key as GroupName}`)}</p>
              <div className="flex flex-wrap gap-1.5">
                {group.variables.map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => pick(name)}
                    className="btn-plain rounded-full border border-border px-2.5 py-1 text-xs font-medium transition-colors hover:border-primary/60 hover:bg-primary/10"
                  >
                    {t(`variables.${name as VariableName}`)}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
