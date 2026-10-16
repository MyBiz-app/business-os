"use client";

import { CalendarClock, ChevronDown, ChevronUp, Pause, Pencil, Play, Trash2, Zap } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { Field } from "@/components/form/field";
import { isolate } from "@/lib/bidi";

import { describeSchedule, type Schedule, weekdayNames } from "./describe-schedule";
import { deleteTask, runTaskNow, type TaskBoard, type TaskCard, type TaskResult, type TaskRun, taskRuns, updateTask } from "./tasks-actions";

type Translate = ReturnType<typeof useTranslations<"aiTeam">>;

const STATUS_TONE: Record<TaskCard["status"], string> = { active: "text-success", paused: "text-muted", done: "text-muted", failed: "text-danger" };
const RUN_TONE: Record<TaskRun["status"], string> = { running: "text-primary", ok: "text-success", failed: "text-danger", skipped: "text-muted" };

function errorText(t: Translate, code: string | null | undefined): string {
  if (!code) return "";
  const key = `tasks.runError.${code}` as "tasks.runError.generic";
  return t.has(key) ? t(key) : t("tasks.runError.generic");
}

/** The scheduled tasks of the AI team: what each agent will do and when, with its history. */
export function TasksBoard({ board, agents, timeZone }: { board: TaskBoard; agents: Record<string, string>; timeZone: string }) {
  const t = useTranslations("aiTeam");
  const locale = useLocale();
  const when = (iso: string | null) => (iso ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso)) : "");
  return (
    <section aria-labelledby="tasks-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h2 id="tasks-title" className="flex items-center gap-2 text-xl font-semibold">
            <CalendarClock aria-hidden="true" className="size-5 text-primary" />
            {t("tasks.title")}
          </h2>
          <p className="max-w-3xl text-sm text-muted">{t("tasks.subtitle")}</p>
        </div>
        <p className="text-sm text-muted">{t("tasks.usage", { active: board.active, limit: board.limit })}</p>
      </div>
      {board.tasks.length === 0 ? (
        <p className="card p-6 text-center text-muted">{t("tasks.empty")}</p>
      ) : (
        <ul className="grid gap-3">
          {board.tasks.map((task) => (
            <TaskRow key={task.id} task={task} agentName={agents[task.agent_key] ?? task.agent_key} when={when} />
          ))}
        </ul>
      )}
      {!board.precise_timing && (
        <p className="flex items-center gap-2 text-xs text-muted">
          <Zap aria-hidden="true" className="size-3.5" />
          {t("tasks.timing")}
        </p>
      )}
    </section>
  );
}

function TaskRow({ task, agentName, when }: { task: TaskCard; agentName: string; when: (iso: string | null) => string }) {
  const t = useTranslations("aiTeam");
  const locale = useLocale();
  const [pending, start] = useTransition();
  const [editing, setEditing] = useState(false);
  const [runs, setRuns] = useState<TaskRun[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const live = task.status === "active" || task.status === "paused";
  const schedule = task.schedule as Schedule;
  const reasonKey = `tasks.reason.${task.status_reason}` as "tasks.reason.cancelled";
  const reason = task.status_reason && t.has(reasonKey) ? t(reasonKey) : null;

  const act = (work: () => Promise<TaskResult>) =>
    start(async () => {
      setMessage(null);
      const result = await work();
      if (!result.ok) setMessage(result.error === "time_passed" ? t("tasks.form.timePassed") : result.error === "invalid" ? t("tasks.form.invalid") : t("tasks.form.failed"));
      else if (runs) setRuns(await taskRuns(task.id));
    });

  const toggleHistory = async () => {
    setRuns(runs === null ? await taskRuns(task.id) : null);
  };

  return (
    <li className="card flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="font-semibold" dir="auto">
            {task.system_key ? t(`tasks.proactive.taskTitle.${task.system_key}`) : task.title}
          </p>
          <p className="text-sm text-muted">
            <span dir="auto">{describeSchedule(schedule, t, locale)}</span>
            {" · "}
            {t(`tasks.kind.${task.kind}`)}
            {" · "}
            <span dir="auto">{t("tasks.agentLabel", { name: isolate(agentName) })}</span>
          </p>
          {task.instruction && !task.system_key && (
            <p className="text-sm" dir="auto">
              {task.instruction}
            </p>
          )}
        </div>
        <span className={`text-sm font-medium ${STATUS_TONE[task.status]}`}>{t(`tasks.status.${task.status}`)}</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
        {live && task.next_run_at && <span>{t("tasks.next", { when: when(task.next_run_at) })}</span>}
        <span>{task.last_run_at ? t("tasks.last", { when: when(task.last_run_at) }) : t("tasks.never")}</span>
        {task.kind === "agent_run" && <span>{t("tasks.creditsCap", { credits: task.max_credits })}</span>}
        {!task.mine && <span>{t("tasks.someoneElse")}</span>}
      </div>
      {reason && <p className="text-sm text-danger">{reason}</p>}
      {task.last_status && task.last_status !== "ok" && task.last_error && (
        <p className="text-sm text-danger" dir="auto">
          {errorText(t, task.last_error)}
        </p>
      )}
      {task.waiting_for_approval > 0 && <p className="text-sm font-medium text-primary">{t("tasks.waiting", { count: task.waiting_for_approval })}</p>}
      {message && (
        <p role="alert" className="text-sm text-danger">
          {message}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {live && (
          <button type="button" disabled={pending} onClick={() => act(() => updateTask(task.id, { status: task.status === "active" ? "paused" : "active" }))} className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
            {task.status === "active" ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
            {task.status === "active" ? t("tasks.pause") : t("tasks.resume")}
          </button>
        )}
        {live && task.mine && (
          <>
            <button type="button" disabled={pending} onClick={() => act(() => runTaskNow(task.id))} className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
              <Zap aria-hidden="true" className="size-4" />
              {pending ? t("tasks.running") : t("tasks.runNow")}
            </button>
            <button type="button" onClick={() => setEditing(!editing)} aria-expanded={editing} className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
              <Pencil aria-hidden="true" className="size-4" />
              {t("tasks.edit")}
            </button>
          </>
        )}
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            if (window.confirm(t("tasks.confirmDelete"))) act(() => deleteTask(task.id));
          }}
          className="btn-ghost inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-danger"
        >
          <Trash2 aria-hidden="true" className="size-4" />
          {t("tasks.delete")}
        </button>
        <button type="button" onClick={toggleHistory} aria-expanded={runs !== null} className="btn-ghost ms-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
          {runs !== null ? <ChevronUp aria-hidden="true" className="size-4" /> : <ChevronDown aria-hidden="true" className="size-4" />}
          {runs !== null ? t("tasks.hideHistory") : t("tasks.history")}
        </button>
      </div>
      {editing && <EditForm task={task} onDone={() => setEditing(false)} act={act} />}
      {runs !== null && <History runs={runs} when={when} />}
    </li>
  );
}

function EditForm({ task, onDone, act }: { task: TaskCard; onDone: () => void; act: (work: () => Promise<TaskResult>) => void }) {
  const t = useTranslations("aiTeam");
  const locale = useLocale();
  const current = task.schedule as Schedule;
  const [frequency, setFrequency] = useState(current.type);
  const [time, setTime] = useState(current.time ?? "08:00");
  const [date, setDate] = useState(current.date ?? "");
  const [weekdays, setWeekdays] = useState<number[]>(current.weekdays ?? [6]);
  const [day, setDay] = useState(current.day ?? 1);
  const [title, setTitle] = useState(task.title);
  const [instruction, setInstruction] = useState(task.instruction ?? "");
  const names = weekdayNames(locale);

  const save = () => {
    act(() =>
      updateTask(task.id, {
        title,
        ...(task.kind === "agent_run" ? { instruction } : {}),
        schedule: { frequency: frequency as "once", time, date: frequency === "once" ? date : null, weekdays: frequency === "weekly" ? weekdays : null, day_of_month: frequency === "monthly" ? day : null },
      }),
    );
    onDone();
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
      className="flex flex-col gap-3 rounded-xl border border-border bg-background p-4"
    >
      <Field label={t("tasks.form.title")} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} required />
      {task.kind === "agent_run" && <Field label={t("tasks.form.instruction")} value={instruction} onChange={(e) => setInstruction(e.target.value)} maxLength={2000} required />}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`freq-${task.id}`} className="text-sm font-medium">
            {t("tasks.form.frequency")}
          </label>
          <select id={`freq-${task.id}`} className="control w-full px-3 py-2" value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            {(["once", "daily", "weekly", "monthly"] as const).map((f) => (
              <option key={f} value={f}>
                {t(`tasks.frequency.${f}`)}
              </option>
            ))}
          </select>
        </div>
        <Field label={t("tasks.form.time")} type="time" value={time} onChange={(e) => setTime(e.target.value)} required />
        {frequency === "once" && <Field label={t("tasks.form.date")} type="date" value={date} onChange={(e) => setDate(e.target.value)} required />}
        {frequency === "monthly" && <Field label={t("tasks.form.day")} type="number" min={1} max={28} value={day} onChange={(e) => setDay(Number(e.target.value))} required />}
      </div>
      {frequency === "weekly" && (
        <fieldset className="flex flex-wrap gap-2">
          <legend className="mb-1 text-sm font-medium">{t("tasks.form.weekdays")}</legend>
          {names.map((name, index) => (
            <label key={index} className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-sm">
              <input type="checkbox" checked={weekdays.includes(index)} onChange={() => setWeekdays((list) => (list.includes(index) ? list.filter((d) => d !== index) : [...list, index].sort()))} />
              {name}
            </label>
          ))}
        </fieldset>
      )}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary px-3 py-1.5 text-sm">
          {t("tasks.form.save")}
        </button>
        <button type="button" onClick={onDone} className="btn-secondary px-3 py-1.5 text-sm">
          {t("tasks.form.cancel")}
        </button>
      </div>
    </form>
  );
}

function History({ runs, when }: { runs: TaskRun[]; when: (iso: string | null) => string }) {
  const t = useTranslations("aiTeam");
  if (runs.length === 0) return <p className="text-sm text-muted">{t("tasks.noRuns")}</p>;
  return (
    <ol className="flex flex-col gap-2 border-s-2 border-border ps-3">
      {runs.map((run) => (
        <li key={run.id} className="flex flex-col gap-0.5 text-sm">
          <p className="flex flex-wrap items-center gap-2">
            <span className={`font-medium ${RUN_TONE[run.status]}`}>{t(`tasks.run.${run.status}`)}</span>
            <span className="text-muted">{when(run.started_at)}</span>
            {run.credits > 0 && <span className="text-muted">{t("tasks.credits", { credits: Math.round(run.credits * 10) / 10 })}</span>}
            {run.pending_action_ids.length > 0 && <span className="text-primary">{t("tasks.waiting", { count: run.pending_action_ids.length })}</span>}
          </p>
          {run.summary && (
            <p className="whitespace-pre-line" dir="auto">
              {run.summary}
            </p>
          )}
          {run.error && (
            <p className="text-danger" dir="auto">
              {errorText(t, run.error)}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
