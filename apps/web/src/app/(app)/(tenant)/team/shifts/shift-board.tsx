"use client";

import { AlertTriangle, ArrowRightLeft, BookmarkPlus, Copy, Plane, Plus, ShieldAlert, Trash2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import { Avatar } from "@/components/avatar";
import { Field, SelectField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { type AvailabilityWindow, outsideAvailability } from "@/lib/availability";
import { formatDay } from "@/lib/dates";

import { copyShiftsDay, copyShiftsWeek, type CopyState, deleteShift, deleteTemplate, saveShift, saveTemplate, type ShiftState, type TemplateState } from "./actions";

export type BoardPerson = { id: string; name: string; title: string; avatar: string | null; homeId: string | null; availability?: AvailabilityWindow[] | null };
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
  stationId: string | null;
  stationName: string | null;
  position: string | null;
  note: string | null;
  isCover: boolean;
  homeName: string | null;
  warning: "timeOff" | "outsideAvailability" | "outsideHours" | null;
  /** Planned but not yet published: only managers see it. */
  draft: boolean;
};
/** Days a person is away, keyed `userId:day`; the value is the reason, if given. */
export type Away = Record<string, string | null>;
export type BoardTemplate = { id: string; locationId: string; name: string; starts: string; ends: string; position: string | null };
/** A named room or post of a branch that shifts are planned into. */
export type BoardStation = { id: string; locationId: string; name: string };
/** A stretch where a branch has fewer people on shift than its coverage rules ask. */
export type BoardGap = { locationId: string; locationName: string; day: string; starts: string; ends: string; startMinute: number; endMinute: number; needed: number; have: number; available?: string[] };
type Branch = { id: string; name: string; color: string };
export type Editing = { shift: BoardShift | null; userId: string; day: string; locationId?: string; stationId?: string };

/** The week's shifts: a row per person, a column per day. Managers add a shift from an empty
 * cell and open one to change or delete it. */
export function ShiftBoard(props: {
  days: string[];
  today: string;
  locale: string;
  people: BoardPerson[];
  shifts: BoardShift[];
  away?: Away;
  branches: Branch[];
  canEdit: boolean;
  weekStart: string;
  copyMode?: "week" | "day" | null;
  compact?: boolean;
  templates?: BoardTemplate[];
  stations?: BoardStation[];
  gaps?: BoardGap[];
}) {
  const { days, today, locale, people, shifts, away = {}, branches, canEdit, weekStart, copyMode = null, compact = false, templates = [], stations = [], gaps = [] } = props;
  const t = useTranslations("shifts");
  const tCommon = useTranslations("common");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [copy, setCopy] = useState<CopyState>({});
  const [copying, startCopy] = useTransition();
  const [copyCount, setCopyCount] = useState(1);
  const copyCounts = copyMode === "week" ? [1, 2, 4] : [1, 3, 6];
  const hours = (minutes: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(minutes / 60);
  const total = (userId: string) => shifts.filter((s) => s.userId === userId).reduce((sum, s) => sum + s.minutes, 0);
  const covered = (day: string) => new Set(shifts.filter((s) => s.day === day).map((s) => s.userId)).size;

  const shiftButton = (shift: BoardShift, person: BoardPerson, day: string) => (
    <button
      key={shift.id}
      type="button"
      disabled={!canEdit}
      onClick={() => setEditing({ shift, userId: person.id, day })}
      className={`flex w-full flex-col items-start rounded-lg border-s-[3px] px-2 py-1 text-start text-xs max-md:min-h-11 transition-shadow hover:shadow-sm disabled:cursor-default ${shift.draft ? "border border-dashed border-border" : ""}`}
      style={{ borderInlineStartColor: shift.color, background: `color-mix(in oklab, ${shift.color} ${shift.draft ? 5 : 12}%, var(--surface))` }}
      aria-label={`${person.name}: ${shift.starts}–${shift.ends} ${shift.locationName}${shift.stationName ? `, ${shift.stationName}` : ""}${shift.position ? `, ${shift.position}` : ""}`}
    >
      <span className="flex w-full items-center gap-1 font-semibold tabular-nums" dir="ltr">
        {shift.starts}–{shift.ends}
        {shift.warning && <AlertTriangle aria-label={t(`warnings.${shift.warning}`)} className="ms-auto size-3.5 text-warning" />}
      </span>
      {(shift.stationName || shift.position || branches.length > 1) && (
        <span dir="auto" className="w-full truncate text-muted">
          {shift.stationName ?? shift.position ?? shift.locationName}
        </span>
      )}
      {shift.draft && <span className="mt-0.5 rounded-full bg-warning/15 px-1.5 text-[0.6875rem] font-medium text-warning">{t("publish.draft")}</span>}
      {shift.isCover && (
        <span className="mt-0.5 inline-flex max-w-full items-center gap-1 rounded-full bg-primary/10 px-1.5 text-[0.6875rem] font-medium text-primary">
          <ArrowRightLeft aria-hidden="true" className="size-3 shrink-0" />
          <span dir="auto" className="truncate">{shift.locationName}</span>
        </span>
      )}
    </button>
  );

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
          {Object.keys(away).length > 0 && (
            <li className="flex items-center gap-1.5">
              <Plane aria-hidden="true" className="size-3.5 text-muted" />
              {t("awayLegend")}
            </li>
          )}
          {gaps.length > 0 && (
            <li className="flex items-center gap-1.5">
              <ShieldAlert aria-hidden="true" className="size-3.5 text-warning" />
              {t("coverage.legend")}
            </li>
          )}
        </ul>
        {canEdit && copyMode && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <label htmlFor="copy-count" className="text-sm text-muted">
                {t("copyTo")}
              </label>
              <select id="copy-count" value={copyCount} onChange={(event) => setCopyCount(Number(event.target.value))} className="input w-auto py-1.5 text-sm">
                {copyCounts.map((n) => (
                  <option key={n} value={n}>
                    {copyMode === "week" ? (n === 1 ? t("copyNextWeek") : t("copyNextWeeks", { count: n })) : n === 1 ? t("copyNextDay") : t("copyNextDays", { count: n })}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={copying || shifts.length === 0}
                aria-busy={copying}
                onClick={() => startCopy(async () => setCopy(await (copyMode === "week" ? copyShiftsWeek(weekStart, copyCount) : copyShiftsDay(weekStart, copyCount))))}
                className="btn-secondary px-3 py-2 text-sm"
              >
                <Copy aria-hidden="true" className="size-4" />
                {t("copyDo")}
              </button>
            </div>
            {copy.copied && (
              <p role="status" className="text-xs text-muted">
                {t("copied", { created: copy.copied.created, skipped: copy.copied.skipped })}
              </p>
            )}
            {copy.error && (
              <p role="alert" className="text-xs text-danger">
                {tCommon("errors.generic")}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="card overflow-x-auto p-0 max-md:hidden">
        <table className="w-full border-collapse text-sm" style={{ minWidth: `${13 + days.length * (compact ? 6 : 7)}rem` }}>
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
                  {gaps.some((g) => g.day === day) && (
                    <span className="mt-0.5 flex items-center justify-center gap-1 text-[0.6875rem] font-medium text-warning" title={t("coverage.short", { count: gaps.filter((g) => g.day === day).length })}>
                      <ShieldAlert aria-hidden="true" className="size-3" />
                      <span className="sr-only">{t("coverage.short", { count: gaps.filter((g) => g.day === day).length })}</span>
                    </span>
                  )}
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
                  const isAway = `${person.id}:${day}` in away;
                  return (
                    <td key={day} className={`group h-16 border-s border-border p-1 align-top ${day === today ? "bg-primary/[0.03]" : ""}`}>
                      <div className="flex h-full flex-col gap-1">
                        {isAway && <AwayChip reason={away[`${person.id}:${day}`]} label={t("away")} />}
                        {mine.map((shift) => shiftButton(shift, person, day))}
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
      <div className="flex flex-col gap-3 md:hidden">
        {days.map((day) => {
          const working = people.filter((p) => shifts.some((s) => s.userId === p.id && s.day === day) || `${p.id}:${day}` in away);
          const label = formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" });
          return (
            <section key={day} aria-label={label} className="card overflow-hidden p-0">
              <h3 className={`flex items-center justify-between gap-2 border-b border-border px-4 py-2.5 text-sm font-semibold ${day === today ? "bg-primary/10 text-primary" : "bg-surface-2"}`}>
                {label}
                <span className="text-xs font-normal text-muted">{t("onShift", { count: covered(day) })}</span>
              </h3>
              {gaps.filter((g) => g.day === day).map((g) => (
                <p key={`${g.locationId}-${g.starts}`} className="flex flex-wrap items-center gap-x-2 border-b border-border bg-warning/10 px-4 py-2 text-xs font-medium text-warning">
                  <ShieldAlert aria-hidden="true" className="size-3.5 shrink-0" />
                  {branches.length > 1 && <span dir="auto">{g.locationName}</span>}
                  <span dir="ltr" className="tabular-nums">{g.starts}–{g.ends}</span>
                  <span>{t("coverage.gap", { have: g.have, needed: g.needed })}</span>
                </p>
              ))}
              <ul className="flex flex-col divide-y divide-border">
                {working.length === 0 && <li className="px-4 py-3 text-sm text-muted">{t("noShiftsDay")}</li>}
                {working.map((person) => (
                  <li key={person.id} className="flex flex-col gap-1.5 px-4 py-2.5">
                    <span className="flex items-center gap-2.5">
                      <Avatar id={person.id} name={person.name} src={person.avatar} size="sm" />
                      <span dir="auto" className="min-w-0 truncate text-sm font-medium">{person.name}</span>
                      {`${person.id}:${day}` in away && <AwayChip reason={away[`${person.id}:${day}`]} label={t("away")} />}
                    </span>
                    {shifts.filter((s) => s.userId === person.id && s.day === day).map((shift) => shiftButton(shift, person, day))}
                  </li>
                ))}
              </ul>
              {canEdit && (
                <button
                  type="button"
                  onClick={() => setEditing({ shift: null, userId: people[0].id, day })}
                  aria-label={t("dayCardAdd", { day: formatDay(day, locale, { weekday: "long", day: "numeric" }) })}
                  className="flex min-h-11 w-full items-center justify-center border-t border-dashed border-border text-muted transition-colors hover:text-foreground"
                >
                  <Plus aria-hidden="true" className="size-4" />
                </button>
              )}
            </section>
          );
        })}
      </div>
      {editing && <ShiftDialog key={`${editing.shift?.id ?? "new"}-${editing.userId}-${editing.day}`} editing={editing} people={people} branches={branches} templates={templates} stations={stations} away={away} onClose={() => setEditing(null)} />}
    </div>
  );
}

function AwayChip({ reason, label }: { reason: string | null; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-[0.6875rem] font-medium text-muted" title={reason ?? undefined}>
      <Plane aria-hidden="true" className="size-3 shrink-0" />
      <span dir="auto" className="truncate">{reason ? `${label} · ${reason}` : label}</span>
    </span>
  );
}

export function ShiftDialog({ editing, people, branches, templates = [], stations = [], away = {}, onClose }: { editing: Editing; people: BoardPerson[]; branches: Branch[]; templates?: BoardTemplate[]; stations?: BoardStation[]; away?: Away; onClose: () => void }) {
  const t = useTranslations("shifts");
  const tCommon = useTranslations("common");
  const dialog = useRef<HTMLDialogElement>(null);
  const { shift } = editing;
  const [state, action] = useActionState<ShiftState, FormData>(saveShift.bind(null, shift?.id ?? null), {});
  const [deleting, startDelete] = useTransition();
  const [picked, setPicked] = useState({ userId: editing.userId, day: editing.day });
  const pickedAway = `${picked.userId}:${picked.day}` in away;
  const [locationId, setLocationId] = useState(shift?.locationId ?? editing.locationId ?? people.find((p) => p.id === editing.userId)?.homeId ?? branches[0]?.id ?? "");
  const [stationId, setStationId] = useState(shift?.stationId ?? editing.stationId ?? "");
  const [starts, setStarts] = useState(shift?.starts ?? "09:00");
  const [ends, setEnds] = useState(shift?.ends ?? "17:00");
  const [position, setPosition] = useState(shift?.position ?? "");
  const pickedPerson = people.find((p) => p.id === picked.userId);
  const pickedOutside = outsideAvailability(pickedPerson?.availability, picked.day, starts, ends);
  const here = templates.filter((tpl) => tpl.locationId === locationId);
  const rooms = stations.filter((s) => s.locationId === locationId);
  const apply = (tpl: BoardTemplate) => {
    setStarts(tpl.starts);
    setEnds(tpl.ends);
    if (tpl.position) setPosition(tpl.position);
  };

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
      <form
        action={action}
        onChange={(event) => {
          const form = event.currentTarget;
          setPicked({ userId: String(new FormData(form).get("user_id")), day: String(new FormData(form).get("day")) });
        }}
        className="flex flex-col gap-4 p-6"
      >
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
          <SelectField label={t("branch")} name="location_id" value={locationId} onChange={(e) => { setLocationId(e.target.value); setStationId(""); }} options={branches.map((b) => ({ value: b.id, label: b.name }))} />
          <Field label={t("date")} name="day" type="date" defaultValue={editing.day} required dir="ltr" />
        </div>
        {branches.length > 1 && <p className="-mt-2 text-xs text-muted">{t("coverHint")}</p>}
        {rooms.length > 0 && <SelectField label={t("stations.field")} name="station_id" value={rooms.some((s) => s.id === stationId) ? stationId : ""} onChange={(e) => setStationId(e.target.value)} options={[{ value: "", label: t("stations.noStation") }, ...rooms.map((s) => ({ value: s.id, label: s.name }))]} />}
        <TemplatePicker templates={here} onApply={apply} />
        <div className="grid grid-cols-2 gap-4">
          <Field label={t("starts")} name="starts" type="time" step={900} value={starts} onChange={(e) => setStarts(e.target.value)} required dir="ltr" />
          <Field label={t("ends")} name="ends" type="time" step={900} value={ends} onChange={(e) => setEnds(e.target.value)} required dir="ltr" />
        </div>
        <Field label={t("position")} name="position" value={position} onChange={(e) => setPosition(e.target.value)} maxLength={60} placeholder={t("positionPlaceholder")} dir="auto" />
        <SaveAsTemplate locationId={locationId} starts={starts} ends={ends} position={position} />
        <Field label={t("note")} name="note" defaultValue={shift?.note ?? ""} maxLength={200} dir="auto" />
        {pickedAway && (
          <p role="status" className="flex items-center gap-2 rounded-xl bg-warning/10 px-3 py-2 text-sm">
            <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-warning" />
            {t("awayWarning", { name: people.find((p) => p.id === picked.userId)?.name ?? "" })}
          </p>
        )}
        {pickedOutside && (
          <p role="status" className="flex items-center gap-2 rounded-xl bg-warning/10 px-3 py-2 text-sm">
            <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-warning" />
            {t("availabilityWarning", { name: pickedPerson?.name ?? "" })}
          </p>
        )}
        {shift?.warning && !(pickedAway && shift.warning === "timeOff") && shift.warning !== "outsideAvailability" && (
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

/** The branch's saved shift types: one click fills the times (and position). */
function TemplatePicker({ templates, onApply }: { templates: BoardTemplate[]; onApply: (template: BoardTemplate) => void }) {
  const t = useTranslations("shifts");
  const [, startDelete] = useTransition();
  if (templates.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">{t("templates.apply")}</span>
      <ul className="flex flex-wrap gap-2">
        {templates.map((tpl) => (
          <li key={tpl.id} className="flex items-center rounded-full border border-border bg-surface-2 text-sm">
            <button type="button" onClick={() => onApply(tpl)} className="rounded-s-full px-3 py-1 font-medium transition-colors hover:text-primary">
              <span dir="auto">{tpl.name}</span> <span dir="ltr" className="tabular-nums text-muted">{tpl.starts}–{tpl.ends}</span>
            </button>
            <button type="button" onClick={() => startDelete(() => deleteTemplate(tpl.id))} aria-label={t("templates.remove", { name: tpl.name })} className="rounded-e-full px-2 py-1 text-muted transition-colors hover:text-danger">
              <X aria-hidden="true" className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Keeps the times above as a named shift type of the branch. */
function SaveAsTemplate({ locationId, starts, ends, position }: { locationId: string; starts: string; ends: string; position: string }) {
  const t = useTranslations("shifts");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [state, setState] = useState<TemplateState>({});
  const [saving, startSave] = useTransition();
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="btn-ghost -mt-1 self-start px-2 py-1 text-sm">
        <BookmarkPlus aria-hidden="true" className="size-4" />
        {t("templates.save")}
      </button>
    );
  }
  const save = () =>
    startSave(async () => {
      const result = await saveTemplate(locationId, name.trim(), starts, ends, position.trim());
      setState(result);
      if (result.saved) {
        setOpen(false);
        setName("");
      }
    });
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-2 p-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-40 flex-1 flex-col gap-1 text-sm font-medium">
          {t("templates.name")}
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder={t("templates.namePlaceholder")} dir="auto" className="control px-3 py-1.5 font-normal" />
        </label>
        <button type="button" disabled={saving || name.trim() === ""} aria-busy={saving} onClick={save} className="btn-primary px-3 py-1.5 text-sm">
          {t("templates.saveDo", { times: `${starts}–${ends}` })}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="btn-ghost px-3 py-1.5 text-sm">
          {t("templates.cancel")}
        </button>
      </div>
      {state.error && (
        <p role="alert" className="text-xs text-danger">
          {state.error === "name_taken" ? t("templates.nameTaken") : t("errors.invalid")}
        </p>
      )}
    </div>
  );
}
