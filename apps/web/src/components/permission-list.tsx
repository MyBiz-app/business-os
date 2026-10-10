import { Check, Minus } from "lucide-react";
import { useTranslations } from "next-intl";

/** Every permission with a mark for whether it is on: for roles and for one person. */
export function PermissionList({ all, allowed }: { all: string[]; allowed: string[] }) {
  const t = useTranslations();
  return (
    <ul className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
      {all.map((permission) => {
        const on = allowed.includes(permission);
        const label = t(`permissions.${permission.replace(".", "_")}` as "permissions.clients_read");
        return (
          <li key={permission} className={`flex items-center gap-2 text-sm ${on ? "" : "text-muted"}`}>
            {on ? <Check aria-hidden="true" className="size-4 text-success" /> : <Minus aria-hidden="true" className="size-4" />}
            <span className={on ? "" : "line-through decoration-muted/50"}>{label}</span>
            <span className="sr-only">{on ? t("team.allowed") : t("team.notAllowed")}</span>
          </li>
        );
      })}
    </ul>
  );
}
