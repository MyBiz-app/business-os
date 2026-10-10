"use client";

import { AlertTriangle, Copy, Plus, Trash2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import { Avatar } from "@/components/avatar";
import { Field, SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { addDays, formatDay } from "@/lib/dates";

import { copyShiftsWeek, type CopyState, deleteShift, saveShift, type ShiftState } from "./actions";

export type BoardPerson = { id: string; name: string; title: string; avatar: string | null };
export type BoardShift = {
  id: string;
  userId: string;
  day: string;
  starts: string;
  ends: string;
  minutes: number;
  locationId: string;
  locationName: string;
  color: string;
  position: string | null;
  note: string | null;
  warning: "timeOff" | "outsideHours" | null;
};
type Branch = { id: string; name: string; color: string };
type Editing = { shift: BoardShift | null; userId: string; day: string };

/** The week's shifts: a row per person, a column per day. Managers add a shift from an empty
 * cell and open one to change or delete it. */
export function ShiftBoard(props: {
  days: string[];
  today: string;
  locale: string;
  people: BoardPerson[];
  shifts: BoardShift[];
  branches: Branch[];
  canEdit: boolean;
  weekStart: string;
}) {
  const { days, today, locale, people, shifts, branches, canEdit, weekStart } = props;
  const t = useTranslations("shifts");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [copy, setCopy] = useState<CopyState>({});
  const [copying, startCopy] = useTransition();
  const hours = (minutes: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(minutes / 60);
  const total = (userId: string) => shifts.filter((s) => s.userId === userId).reduce((sum, s) => sum + s.minutes, 0);
  const covered = (day: string) => new Set(shifts.filter((s) => s.day === day).map((s) => s.userId)).size;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap items-center gap-3 text-xs text-muted">
          {branches.length > 1 &&
            branches.map((b) => (
              <li key={b.id} className="flex items-center gap-1.5">
                <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: b.color }} />
                <span dir="auto">{b.name}</span>
              </li>
            ))}
          <li className="flex items-center gap-1.5">
            <AlertTriangle aria-hidden="true" className="size-3.5 text-warning" />
            {t("warningLegend")}
          </li>
        </ul>
        {canEdit && (
          <div className="flex flex-col items-end gap-1">
            <button
              type="button"
              disabled={copying || shifts.length === 0}
              aria-busy={copying}
              onClick={() => startCopy(async () => setCopy(await copyShiftsWeek(weekStart, addDays(weekStart, 7))))}
              className="btn-secondary px-3 py-2 text-sm"
            >
              <Copy aria-hidden="true" className="size-4" />
              {t("copyWeek")}
            </button>
            {copy.copied && (
              <p role="status" className="text-xs text-muted">
                {t("copied", { created: copy.copied.created, skipped: copy.copied.skipped })}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[56rem] border-collapse text-sm">
          <caption className="sr-only">{t("title")}</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="w-52 px-4 py-3 text-start font-medium text-muted">
                {t("person")}
              </th>
              {days.map((day) => (
                <th key={day} scope="col" className={`px-2 py-3 text-center font-medium ${day === today ? "text-primary" : "text-muted"}`}>
                  <span className="block">{formatDay(day, locale, { weekday: "short" })}</span>
                  <span className={`mx-auto mt-0.5 flex size-7 items-center justify-center rounded-full text-sm font-semibold tabular-nums ${day === today ? "bg-primary text-on-primary" : "text-foreground"}`}>
                    {formatDay(day, locale, { day: "numeric" })}
                  </span>
                  <span className="mt-0.5 block text-[0.6875rem] font-normal">{t("onShift", { count: covered(day) })}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {people.map((person) => (
              <tr key={person.id} className="border-b border-border last:border-b-0">
                <th scope="row" className="px-4 py-2 text-start font-normal">
                  <span className="flex items-center gap-2.5">
                    <Avatar id={person.id} name={person.name} src={person.avatar} size="sm" />
                    <span className="flex min-w-0 flex-col">
                      <span dir="auto" className="truncate font-medium">
                        {person.name}
                      </span>
                      <span className="truncate text-xs text-muted">
                        {person.title} · {t("hoursTotal", { hours: hours(total(person.id)) })}
                      </span>
                    </span>
                  </span>
                </th>
                {days.map((day) => {
                  const mine = shifts.filter((s) => s.userId === person.id && s.day === day);
                  return (
                    <td key={day} className={`group h-16 border-s border-border p-1 align-top ${day === today ? "bg-primary/[0.03]" : ""}`}>
                      <div className="flex h-full flex-col gap-1">
                        {mine.map((shift) => (
                          <button
                            key={shift.id}
                            type="button"
                            disabled={!canEdit}
                            onClick={() => setEditing({ shift, userId: person.id, day })}
                            className="flex w-full flex-col items-start rounded-lg border-s-[3px] px-2 py-1 text-start text-xs transition-shadow hover:shadow-sm disabled:cursor-default"
                            style={{ borderInlineStartColor: shift.color, background: `color-mix(in oklab, ${shift.color} 12%, var(--surface))` }}
                            aria-label={`${person.name}: ${shift.starts}–${shift.ends} ${shift.locationName}${shift.position ? `, ${shift.position}` : ""}`}
                          >
                            <span className="flex w-full items-center gap-1 font-semibold tabular-nums" dir="ltr">
                              {shift.starts}–{shift.ends}
                              {shift.warning && <AlertTriangle aria-label={t(`warnings.${shift.warning}`)} className="ms-auto size-3.5 text-warning" />}
                            </span>
                            {(shift.position || branches.length > 1) && (
                              <span dir="auto" className="w-full truncate text-muted">
                                {shift.position ?? shift.locationName}
                              </span>
                            )}
                          </button>
                        ))}
                        {canEdit && (
                          <button
                            type="button"
                            onClick={() => setEditing({ shift: null, userId: person.id, day })}
                            aria-label={t("addFor", { name: person.name, day: formatDay(day, locale, { weekday: "long", day: "numeric" }) })}
                            className={`flex flex-1 items-center justify-center rounded-lg border border-dashed border-transparent text-muted transition-colors hover:border-border hover:text-foreground focus-visible:border-border ${mine.length ? "min-h-6 opacity-0 group-hover:opacity-100 focus-visible:opacity-100" : "min-h-12 opacity-40 group-hover:opacity-100"}`}
                          >
                            <Plus aria-hidden="true" className="size-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <ShiftDialog key={`${editing.shift?.id ?? "new"}-${editing.userId}-${editing.day}`} editing={editing} people={people} branches={branches} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ShiftDialog({ editing, people, branches, onClose }: { editing: Editing; people: BoardPerson[]; branches: Branch[]; onClose: () => void }) {
  const t = useTranslations("shifts");
  const tCommon = useTranslations("common");
  const dialog = useRef<HTMLDialogElement>(null);
  const { shift } = editing;
  const [state, action] = useActionState<ShiftState, FormData>(saveShift.bind(null, shift?.id ?? null), {});
  const [deleting, startDelete] = useTransition();

  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    if (state.saved) onClose();
  }, [state.saved, onClose]);

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) dialog.current?.close();
      }}
      aria-labelledby="shift-dialog-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-2xl border border-border bg-surface p-0 text-foreground shadow-2xl backdrop:bg-black/40 backdrop:backdrop-blur-sm"
    >
      <form action={action} className="flex flex-col gap-4 p-6">
        <div className="flex items-start justify-between gap-3">
          <h2 id="shift-dialog-title" className="text-lg font-semibold">
            {shift ? t("editTitle") : t("newTitle")}
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} aria-label={t("close")} className="btn-ghost size-8">
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <FormError
          message={state.error && (state.error === "shift_overlap" ? t("errors.overlap") : state.error === "invalid" ? t("errors.invalid") : tCommon("errors.generic"))}
        />
        <SelectField label={t("person")} name="user_id" defaultValue={editing.userId} options={people.map((p) => ({ value: p.id, label: p.name }))} />
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label={t("branch")} name="location_id" defaultValue={shift?.locationId ?? branches[0]?.id} options={branches.map((b) => ({ value: b.id, label: b.name }))} />
          <Field label={t("date")} name="day" type="date" defaultValue={editing.day} required dir="ltr" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label={t("starts")} name="starts" type="time" step={900} defaultValue={shift?.starts ?? "09:00"} required dir="ltr" />
          <Field label={t("ends")} name="ends" type="time" step={900} defaultValue={shift?.ends ?? "17:00"} required dir="ltr" />
        </div>
        <Field label={t("position")} name="position" defaultValue={shift?.position ?? ""} maxLength={60} placeholder={t("positionPlaceholder")} dir="auto" />
        <Field label={t("note")} name="note" defaultValue={shift?.note ?? ""} maxLength={200} dir="auto" />
        {shift?.warning && (
          <p className="flex items-center gap-2 rounded-xl bg-warning/10 px-3 py-2 text-sm">
            <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-warning" />
            {t(`warnings.${shift.warning}`)}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          {shift ? (
            <button
              type="button"
              disabled={deleting}
              aria-busy={deleting}
              onClick={() =>
                startDelete(async () => {
                  await deleteShift(shift.id);
                  onClose();
                })
              }
              className="btn-danger px-3 py-2 text-sm"
            >
              <Trash2 aria-hidden="true" className="size-4" />
              {t("delete")}
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button type="button" onClick={() => dialog.current?.close()} className="btn-ghost px-3 py-2 text-sm">
              {tCommon("cancel")}
            </button>
            <SubmitButton className="px-4 py-2 text-sm">{tCommon("save")}</SubmitButton>
          </div>
        </div>
      </form>
    </dialog>
  );
}
