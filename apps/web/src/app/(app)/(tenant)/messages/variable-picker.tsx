"use client";

import { Braces } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";

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
  const [fallback, setFallback] = useState("");

  return (
    <Popover
      label={t("addVariable")}
      className="flex max-h-80 w-72 flex-col gap-3 overflow-y-auto p-3"
      trigger={(props) => (
        <Button {...props} variant="secondary" className="rounded-full bg-primary-subtle px-3 text-primary-ink">
          <Braces aria-hidden="true" className="size-3.5" />
          {t("addVariable")}
        </Button>
      )}
    >
      {({ close }) => {
        const pick = (name: string) => {
          const value = fallback.trim().replace(/[{}|]/g, "");
          onPick(value ? `{${name}|${value}}` : `{${name}}`);
          close();
        };
        return (
          <>
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
                    <Button key={name} variant="plain" onClick={() => pick(name)} className="rounded-full border border-border px-2.5 py-1 text-xs font-medium transition-colors hover:border-primary/60 hover:bg-primary-subtle">
                      {t(`variables.${name as VariableName}`)}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          </>
        );
      }}
    </Popover>
  );
}
