"use client";

import { formatMoney, toMinorUnits } from "@business-os/i18n/money";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Field, SelectField } from "@/components/form/field";

import { type BonusError, type BonusInput, type BonusPreview, addBonus, previewBonus } from "./actions";

const TARGETS = ["employee", "location", "location_group", "managers", "role", "everyone", "manual"] as const;
const KINDS = ["bonus", "holiday_gift", "expense_refund", "deduction"] as const;
const ROLES = ["owner", "manager", "branch_manager", "front_desk", "staff"] as const;
type Named = { id: string; name: string };

/** Adds a one-off amount to a person or a whole group: pick who, what and how much, look at who
 * would get what, then add it (or, for a branch manager, propose it to the owner). */
export function BonusForm({
  currency,
  locale,
  month,
  canManage,
  members,
  branches,
  groups,
}: {
  currency: string;
  locale: string;
  month: string;
  canManage: boolean;
  members: Named[];
  branches: Named[];
  groups: Named[];
}) {
  const t = useTranslations("payBonuses");
  const router = useRouter();
  const [target, setTarget] = useState<(typeof TARGETS)[number]>("location");
  const [employee, setEmployee] = useState(members[0]?.id ?? "");
  const [picked, setPicked] = useState<string[]>([]);
  const [location, setLocation] = useState(branches[0]?.id ?? "");
  const [group, setGroup] = useState(groups[0]?.id ?? "");
  const [role, setRole] = useState<(typeof ROLES)[number]>("staff");
  const [kind, setKind] = useState<(typeof KINDS)[number]>("bonus");
  const [payMonth, setPayMonth] = useState(month);
  const [mode, setMode] = useState<"each" | "split_total">("each");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<BonusPreview | null>(null);
  const [error, setError] = useState<BonusError | null>(null);
  const [done, setDone] = useState<"added" | "proposed" | null>(null);
  const [pending, startTransition] = useTransition();

  function build(): BonusInput | null {
    const minor = toMinorUnits(amount, currency);
    if (!amount || !minor) {
      setError("amount_required");
      return null;
    }
    const body: Record<(typeof TARGETS)[number], BonusInput["target"]> = {
      employee: { kind: "employee", user_ids: [employee] },
      manual: { kind: "manual", user_ids: picked },
      location: { kind: "location", location_id: location },
      location_group: { kind: "location_group", group_id: group },
      role: { kind: "role", role },
      managers: { kind: "managers" },
      everyone: { kind: "everyone" },
    };
    return {
      target: body[target],
      kind,
      period: `${payMonth}-01`,
      amount_mode: mode,
      amount_minor: minor,
      currency,
      note: note.trim() || null,
    };
  }

  function run(action: "preview" | "add") {
    const input = build();
    if (!input) return;
    setError(null);
    setDone(null);
    startTransition(async () => {
      if (action === "preview") {
        const result = await previewBonus(input);
        setPreview(result.data ?? null);
        setError(result.error ?? null);
        return;
      }
      const result = await addBonus(input);
      setError(result.error ?? null);
      if (result.data) {
        setPreview(null);
        setAmount("");
        setNote("");
        setDone(result.data.status === "proposed" ? "proposed" : "added");
        router.refresh();
      }
    });
  }

  const pickers: Record<(typeof TARGETS)[number], React.ReactNode> = {
    employee: (
      <SelectField label={t("pickEmployee")} value={employee} onChange={(event) => setEmployee(event.target.value)} options={members.map((m) => ({ value: m.id, label: m.name }))} />
    ),
    location: (
      <SelectField label={t("pickLocation")} value={location} onChange={(event) => setLocation(event.target.value)} options={branches.map((b) => ({ value: b.id, label: b.name }))} />
    ),
    location_group: (
      <SelectField label={t("pickGroup")} value={group} onChange={(event) => setGroup(event.target.value)} options={groups.map((g) => ({ value: g.id, label: g.name }))} />
    ),
    role: (
      <SelectField label={t("pickRole")} value={role} onChange={(event) => setRole(event.target.value as (typeof ROLES)[number])} options={ROLES.map((value) => ({ value, label: t(`roles.${value}`) }))} />
    ),
    manual: (
      <fieldset className="flex flex-col gap-1 text-sm">
        <legend className="mb-1 font-medium">{t("pickMembers")}</legend>
        <div className="grid max-h-48 gap-1 overflow-y-auto sm:grid-cols-2">
          {members.map((m) => (
            <label key={m.id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={picked.includes(m.id)}
                onChange={(event) => setPicked(event.target.checked ? [...picked, m.id] : picked.filter((id) => id !== m.id))}
              />
              {m.name}
            </label>
          ))}
        </div>
      </fieldset>
    ),
    managers: null,
    everyone: null,
  };

  return (
    <form
      className="card flex flex-col gap-5 p-6"
      onSubmit={(event) => {
        event.preventDefault();
        run("preview");
      }}
    >
      <h2 className="text-lg font-semibold">{t("newTitle")}</h2>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">{t("target.label")}</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {TARGETS.map((value) => (
            <label key={value} className="flex items-center gap-2">
              <input type="radio" name="target" checked={target === value} onChange={() => { setTarget(value); setPreview(null); }} />
              {t(`target.${value}`)}
            </label>
          ))}
        </div>
      </fieldset>
      {pickers[target]}

      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label={t("kind")}
          value={kind}
          onChange={(event) => setKind(event.target.value as (typeof KINDS)[number])}
          options={KINDS.map((value) => ({ value, label: t(`kinds.${value}`) }))}
        />
        <Field label={t("month")} type="month" value={payMonth} onChange={(event) => setPayMonth(event.target.value)} required />
        <SelectField
          label={t("amountModeLabel")}
          value={mode}
          onChange={(event) => setMode(event.target.value as typeof mode)}
          options={(["each", "split_total"] as const).map((value) => ({ value, label: t(`amountMode.${value}`) }))}
        />
        <Field label={`${t("amount")} (${currency})`} inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} required />
        <Field label={t("note")} value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} />
      </div>

      <p className="-mt-2 text-sm text-muted">{t(`kindHints.${kind}`)}</p>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {t(`errors.${error}`)}
        </p>
      )}
      {done && (
        <p role="status" className="text-sm text-success-ink">
          {done === "proposed" ? t("proposedDone") : t("addedDone")}
        </p>
      )}

      {preview && (
        <div className="flex flex-col gap-2 rounded-xl bg-surface-muted p-4 text-sm">
          <p className="font-medium">
            {t("previewResult", { count: preview.recipients.length, total: formatMoney(preview.total_minor, currency, locale) })}
          </p>
          {preview.without_payroll_file > 0 && <p className="text-muted">{t("withoutFile", { count: preview.without_payroll_file })}</p>}
          {preview.out_of_reach > 0 && <p className="text-muted">{t("outOfReach", { count: preview.out_of_reach })}</p>}
          <ul aria-label={t("recipientsLabel")} className="grid gap-1 sm:grid-cols-2">
            {preview.recipients.map((r) => (
              <li key={r.user_id} className="flex justify-between gap-3">
                <span>{r.full_name ?? r.email}</span>
                <bdi>{formatMoney(r.amount_minor, currency, locale)}</bdi>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn-secondary px-4 py-2" disabled={pending}>
          {t("preview")}
        </button>
        {preview && (
          <button type="button" className="btn-primary px-4 py-2" disabled={pending} onClick={() => run("add")}>
            {canManage ? t("submit", { count: preview.recipients.length }) : t("propose", { count: preview.recipients.length })}
          </button>
        )}
      </div>
    </form>
  );
}
