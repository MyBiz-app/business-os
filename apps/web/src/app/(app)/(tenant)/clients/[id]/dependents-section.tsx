import { PawPrint, Plus, Users } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { setDependentActive } from "./dependents-actions";
import { DependentForm } from "./dependents-forms";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Props = { clientId: string; context: Context; locked: boolean };

/** Whole years from a date of birth to today. */
function yearsSince(birthDate: string): number {
  const born = new Date(`${birthDate}T00:00:00`);
  const now = new Date();
  const years = now.getFullYear() - born.getFullYear();
  const before = now.getMonth() < born.getMonth() || (now.getMonth() === born.getMonth() && now.getDate() < born.getDate());
  return Math.max(0, before ? years - 1 : years);
}

/** The client's pets or children (when the industry keeps them): who actually comes. */
export async function DependentsSection({ clientId, context, locked }: Props) {
  const { api, scope, tenant } = context;
  const settings = unwrap(await api.GET("/dependents/settings", { params: scope }));
  const kind = settings.kind;
  if (!kind) return null;
  const t = await getTranslations("dependents");
  const tFields = await getTranslations("clientFields");
  const locale = await getLocale();
  const dependents = unwrap(
    await api.GET("/clients/{client_id}/dependents", { params: { ...scope, path: { client_id: clientId } } }),
  );
  const writable = !locked && canWriteClients(tenant);
  const Icon = kind === "pet" ? PawPrint : Users;
  const shown = (key: string, value: string | number) => {
    const field = settings.fields.find((f) => f.key === key);
    if (!field) return null;
    const text =
      field.kind === "select"
        ? tFields(`${key}_options.${value}` as "goal_options.strength")
        : field.kind === "number"
          ? new Intl.NumberFormat(locale).format(Number(value))
          : String(value);
    return `${tFields(key as "goal")}: ${text}`;
  };

  return (
    <section aria-labelledby="dependents-heading" className="flex flex-col gap-4 card p-6">
      <h2 id="dependents-heading" className="flex items-center gap-2 text-lg font-semibold">
        <Icon aria-hidden="true" className="size-5 text-primary" />
        {t(`title.${kind}`)}
      </h2>
      {dependents.length === 0 && <p className="text-sm text-muted">{t(`none.${kind}`)}</p>}
      <ul className="flex flex-col gap-3">
        {dependents.map((dependent) => {
          const facts = [
            dependent.birth_date ? t("age", { years: yearsSince(dependent.birth_date) }) : null,
            ...Object.entries(dependent.details).map(([key, value]) => shown(key, value)),
          ].filter(Boolean);
          return (
            <li key={dependent.id} className="flex flex-col gap-2 rounded-xl border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span dir="auto" className="font-semibold">{dependent.name}</span>
                  {!dependent.active && <Pill tone="muted">{t("inactive")}</Pill>}
                </div>
                {writable && (
                  <form action={setDependentActive.bind(null, clientId, dependent.id, !dependent.active)}>
                    <button
                      type="submit"
                      aria-label={`${dependent.active ? t("retire") : t("restore")} – ${dependent.name}`}
                      className="btn-secondary px-2.5 py-1 text-xs"
                    >
                      {dependent.active ? t("retire") : t("restore")}
                    </button>
                  </form>
                )}
              </div>
              {facts.length > 0 && <p className="text-sm text-muted">{facts.join(" · ")}</p>}
              {dependent.notes && <p dir="auto" className="whitespace-pre-line text-sm">{dependent.notes}</p>}
              {writable && (
                <details>
                  <summary className="cursor-pointer text-sm text-primary">{t("edit", { name: dependent.name })}</summary>
                  <div className="pt-3">
                    <DependentForm clientId={clientId} kind={kind} fields={settings.fields} dependent={dependent} />
                  </div>
                </details>
              )}
            </li>
          );
        })}
      </ul>
      {writable && (
        <details className="rounded-xl bg-foreground/[0.03] p-3">
          <summary className="flex cursor-pointer items-center gap-1 text-sm font-medium text-primary">
            <Plus aria-hidden="true" className="size-4" /> {t(`add.${kind}`)}
          </summary>
          <div className="pt-3">
            <DependentForm clientId={clientId} kind={kind} fields={settings.fields} />
          </div>
        </details>
      )}
    </section>
  );
}
