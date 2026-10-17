"use client";

import { useTranslations } from "next-intl";
import { useId, useState, useTransition } from "react";

import { FileField } from "@/components/form/file-field";

import { ConciergePanel, FollowUpPanel } from "./follow-up";
import {
  aiMapMoveFile,
  removeMoveFile,
  runMove,
  startMove,
  undoBatch,
  updateMoveFile,
  uploadMoveFile,
  type AiMap,
  type MoveFile,
  type MoveKind,
  type MoveReport,
  type MoveSession,
  type UndoReport,
} from "./actions";

const ORIGINS = ["spreadsheet", "google", "other_system", "notebook"] as const;
const KINDS: MoveKind[] = ["clients", "memberships", "services", "staff", "appointments"];
const CONTROL = "w-full min-w-0 control px-3 py-2";
type Batch = MoveSession["batches"][number];
/** Message groups picked by a value that comes from the API (codes, fields); unknown ones fall back. */
type Lookup = (group: string, key: string, fallback: string) => string;
function useLookup(): Lookup {
  const t = useTranslations("migration") as unknown as ((key: string) => string) & { has: (key: string) => boolean };
  return (group, key, fallback) => (t.has(`${group}.${key}`) ? t(`${group}.${key}`) : fallback);
}

/** The moving flow: confirm the right to transfer, add files, check what each is, dry run, import. */
export function MigrationHub({ draft, movedId, batches, timeZone }: { draft: MoveSession | null; movedId: string | null; batches: Batch[]; timeZone: string }) {
  const t = useTranslations("migration");
  const word = useLookup();
  const [session, setSession] = useState<MoveSession | null>(draft);
  const [files, setFiles] = useState<MoveFile[]>(draft?.files ?? []);
  const [report, setReport] = useState<MoveReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  // What the AI chose per file (how sure it was), shown next to the columns until the page reloads.
  const [aiNotes, setAiNotes] = useState<Record<string, Pick<AiMap, "confidence" | "source">>>({});
  const [pending, startTransition] = useTransition();

  const fail = (code?: string) => setError(code ?? "generic");
  const act = (work: () => Promise<void>) =>
    startTransition(async () => {
      setError(null);
      await work();
    });

  const replace = (file: MoveFile) => {
    setFiles((current) => current.map((f) => (f.id === file.id ? file : f)));
    setReport(null);
  };

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          {word("errors", error, t("errors.generic"))}
        </p>
      )}

      {report?.committed ? (
        <>
          <Done report={report} onAgain={() => { setSession(null); setFiles([]); setReport(null); }} />
          {session && <FollowUpPanel sessionId={session.id} timeZone={timeZone} />}
        </>
      ) : !session ? (
        <>
          {movedId && <FollowUpPanel sessionId={movedId} timeZone={timeZone} />}
        <Start
          pending={pending}
          onStart={(origin) =>
            act(async () => {
              const result = await startMove(origin);
              if (result.data) setSession(result.data);
              else fail(result.error);
            })
          }
        />
        </>
      ) : (
        <>
          <section aria-labelledby="files-heading" className="flex flex-col gap-4 card p-6">
            <div className="flex flex-col gap-1">
              <h2 id="files-heading" className="text-lg font-semibold">{t("files.title")}</h2>
              <p className="text-sm text-muted">{t("files.hint")}</p>
            </div>
            <FileField
              label={t("files.add")}
              hint={t("files.fileHint")}
              accept=".csv,.xlsx,.vcf,.ics,text/csv,text/vcard,text/calendar,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                const chosen = event.target.files?.[0];
                event.target.value = "";
                if (!chosen) return;
                act(async () => {
                  const body = new FormData();
                  body.set("file", chosen);
                  const result = await uploadMoveFile(session.id, body);
                  if (result.data) {
                    setFiles((current) => [...current, result.data!]);
                    setReport(null);
                  } else fail(result.error);
                });
              }}
            />
            <ul className="flex flex-col gap-4">
              {files.map((file) => (
                <FileCard
                  key={file.id}
                  file={file}
                  pending={pending}
                  ai={aiNotes[file.id]}
                  onAiMap={() =>
                    act(async () => {
                      const result = await aiMapMoveFile(session.id, file.id);
                      if (result.data) {
                        setAiNotes((current) => ({ ...current, [file.id]: result.data! }));
                        replace(result.data.file);
                      } else fail(result.error);
                    })
                  }
                  onChange={(change) =>
                    act(async () => {
                      const result = await updateMoveFile(session.id, file.id, change);
                      if (result.data) replace(result.data);
                      else fail(result.error);
                    })
                  }
                  onRemove={() =>
                    act(async () => {
                      const result = await removeMoveFile(session.id, file.id);
                      if (result.data) {
                        setFiles((current) => current.filter((f) => f.id !== file.id));
                        setReport(null);
                      } else fail(result.error);
                    })
                  }
                />
              ))}
            </ul>
          </section>

          {files.length > 0 && (
            <section aria-labelledby="check-heading" className="flex flex-col gap-4 card p-6">
              <div className="flex flex-col gap-1">
                <h2 id="check-heading" className="text-lg font-semibold">{t("check.title")}</h2>
                <p className="text-sm text-muted">{t("check.hint")}</p>
              </div>
              <div>
                <button
                  type="button"
                  className="btn-secondary px-4 py-2.5"
                  disabled={pending || files.some((f) => !f.kind)}
                  aria-busy={pending}
                  onClick={() =>
                    act(async () => {
                      const result = await runMove(session.id, false);
                      if (result.data) setReport(result.data);
                      else fail(result.error);
                    })
                  }
                >
                  {pending ? t("check.working") : t("check.run")}
                </button>
                {files.some((f) => !f.kind) && <p className="mt-2 text-sm text-muted">{t("check.chooseKinds")}</p>}
              </div>
              {report && <Report report={report} />}
              {report && (
                <div>
                  <button
                    type="button"
                    className="btn-primary px-4 py-2.5"
                    disabled={pending || report.files.every((f) => f.ready === 0)}
                    aria-busy={pending}
                    onClick={() =>
                      act(async () => {
                        const result = await runMove(session.id, true);
                        if (result.data) setReport(result.data);
                        else fail(result.error);
                      })
                    }
                  >
                    {t("check.import", { count: report.files.reduce((sum, f) => sum + f.ready, 0) })}
                  </button>
                </div>
              )}
            </section>
          )}
          {files.length > 0 && <ConciergePanel sessionId={session.id} timeZone={timeZone} />}
        </>
      )}

      {batches.length > 0 && <Batches batches={batches} timeZone={timeZone} onError={fail} />}
    </div>
  );
}

function Start({ pending, onStart }: { pending: boolean; onStart: (origin: string) => void }) {
  const t = useTranslations("migration");
  const word = useLookup();
  const [origin, setOrigin] = useState<string>(ORIGINS[0]);
  const [confirmed, setConfirmed] = useState(false);
  const originId = useId();
  const rightsId = useId();
  return (
    <section aria-labelledby="start-heading" className="flex flex-col gap-4 card p-6">
      <h2 id="start-heading" className="text-lg font-semibold">{t("start.title")}</h2>
      <div className="flex max-w-sm flex-col gap-1.5">
        <label htmlFor={originId} className="text-sm font-medium">{t("start.origin")}</label>
        <select id={originId} value={origin} onChange={(event) => setOrigin(event.target.value)} className={CONTROL}>
          {ORIGINS.map((value) => (
            <option key={value} value={value}>{t(`start.origins.${value}`)}</option>
          ))}
        </select>
      </div>
      <div className="flex items-start gap-3">
        <input id={rightsId} type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1 size-4" />
        <label htmlFor={rightsId} className="text-sm">{t("start.rights")}</label>
      </div>
      <div className="flex flex-col gap-1 rounded-lg bg-surface-2 p-3">
        <p className="text-sm font-medium">{t("start.guideTitle")}</p>
        <p className="text-sm text-muted">{word("start.guides", origin, "")}</p>
      </div>
      <p className="text-sm text-muted">{t("start.privacy")}</p>
      <div>
        <button type="button" className="btn-primary px-4 py-2.5" disabled={pending || !confirmed} aria-busy={pending} onClick={() => onStart(origin)}>
          {t("start.begin")}
        </button>
      </div>
    </section>
  );
}

function FileCard({
  file,
  pending,
  ai,
  onAiMap,
  onChange,
  onRemove,
}: {
  file: MoveFile;
  pending: boolean;
  ai?: Pick<AiMap, "confidence" | "source">;
  onAiMap: () => void;
  onChange: (change: { kind?: MoveKind; mapping?: (string | null)[] }) => void;
  onRemove: () => void;
}) {
  const t = useTranslations("migration");
  const word = useLookup();
  const remap = (column: number, value: string) => {
    const target = value || null;
    // A field can feed only one column: picking it here clears it elsewhere.
    onChange({ mapping: file.mapping.map((current, i) => (i === column ? target : current === target ? null : current)) });
  };
  const unmapped = !file.kind || file.mapping.some((field) => !field);
  return (
    <li className="flex flex-col gap-3 rounded-xl border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium" dir="auto">{file.filename}</p>
          <p className="text-sm text-muted">{t("files.rows", { count: file.rows })}</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            aria-label={t("files.kind")}
            value={file.kind ?? ""}
            disabled={pending}
            onChange={(event) => event.target.value && onChange({ kind: event.target.value as MoveKind })}
            className="control px-3 py-2"
          >
            {!file.kind && <option value="">{t("files.unknownKind")}</option>}
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>{t(`kinds.${kind}`)}</option>
            ))}
          </select>
          <button type="button" className="text-sm text-danger underline-offset-4 hover:underline" disabled={pending} onClick={onRemove}>
            {t("files.remove")}
          </button>
        </div>
      </div>
      {unmapped && (
        <div className="flex flex-col gap-1">
          <div>
            <button type="button" className="btn-secondary px-3 py-2 text-sm" disabled={pending} aria-busy={pending} onClick={onAiMap}>
              {t("files.aiMap")}
            </button>
          </div>
          <p className="text-sm text-muted">{t("files.aiHint")}</p>
        </div>
      )}
      {file.kind && (
        <ul className="flex flex-col divide-y divide-border">
          {file.columns.map((column, i) => {
            const name = column.name || t("files.noHeader", { number: i + 1 });
            return (
              <li key={i} className="grid gap-2 py-2 sm:grid-cols-2 sm:items-center">
                <div className="flex min-w-0 flex-col">
                  <span className="font-medium" dir="auto">{name}</span>
                  {ai?.source[i] === "ai" && (
                    <span className="text-sm font-medium text-muted">{t("files.aiChose", { percent: Math.round((ai.confidence[i] ?? 0) * 100) })}</span>
                  )}
                  {column.example && <span className="truncate text-sm text-muted" dir="auto">{t("files.example", { value: column.example })}</span>}
                </div>
                <select aria-label={t("files.fieldFor", { column: name })} value={file.mapping[i] ?? ""} disabled={pending} onChange={(event) => remap(i, event.target.value)} className={CONTROL}>
                  <option value="">{t("files.ignore")}</option>
                  {file.fields.map((field) => (
                    <option key={field} value={field}>{word("fields", field, field)}</option>
                  ))}
                </select>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

function Report({ report }: { report: MoveReport }) {
  const t = useTranslations("migration");
  const word = useLookup();
  return (
    <div className="flex flex-col gap-4">
      {report.files.map((file) => (
        <div key={file.import_file_id} className="flex flex-col gap-2 rounded-xl border border-border p-4">
          <p className="font-medium" dir="auto">
            {file.filename}
            {file.kind && <span className="text-muted"> · {word("kinds", file.kind, file.kind)}</span>}
          </p>
          <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <li>{t("check.rows", { count: file.rows })}</li>
            <li className="font-semibold">{t("check.ready", { count: file.ready })}</li>
            <li>{t("check.duplicates", { count: file.duplicates })}</li>
            <li>{t("check.invalid", { count: file.invalid })}</li>
            <li>{t("check.skipped", { count: file.skipped })}</li>
          </ul>
          {file.sample.length > 0 && (
            <ul className="text-sm text-muted" dir="auto">
              {file.sample.map((row, i) => (
                <li key={i}>{Object.values(row).join(" · ")}</li>
              ))}
            </ul>
          )}
          {file.issues.length > 0 && (
            <ul className="text-sm text-muted">
              {file.issues.map((issue, i) => (
                <li key={i}>
                  {t("check.issue", { line: issue.line, problem: word("problems", issue.code, issue.code) })}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

function Done({ report, onAgain }: { report: MoveReport; onAgain: () => void }) {
  const t = useTranslations("migration");
  const [copied, setCopied] = useState<string | null>(null);
  const link = (token: string) => `${window.location.origin}/invite/${token}`;
  return (
    <section role="status" className="flex flex-col gap-4 card p-6">
      <h2 className="text-lg font-semibold">{t("done.title", { count: report.files.reduce((sum, f) => sum + f.ready, 0) })}</h2>
      <Report report={report} />
      {report.invitations.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">{t("done.invitations")}</h3>
          <p className="text-sm text-muted">{t("done.inviteHint")}</p>
          <ul className="flex flex-col gap-2 text-sm">
            {report.invitations.map((invitation) => (
              <li key={invitation.email} className="flex flex-wrap items-center justify-between gap-2">
                <span dir="auto">{invitation.email}</span>
                <button
                  type="button"
                  className="btn-secondary px-3 py-1.5"
                  onClick={async () => {
                    await navigator.clipboard.writeText(link(invitation.token));
                    setCopied(invitation.email);
                  }}
                >
                  {copied === invitation.email ? t("done.copied") : t("done.copy")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-sm text-muted">{t("done.undoHint")}</p>
      <div>
        <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={onAgain}>
          {t("done.again")}
        </button>
      </div>
    </section>
  );
}

function Batches({ batches, timeZone, onError }: { batches: Batch[]; timeZone: string; onError: (code?: string) => void }) {
  const t = useTranslations("migration");
  const [pending, startTransition] = useTransition();
  const [includeEdited, setIncludeEdited] = useState(false);
  const [preview, setPreview] = useState<{ id: string; report: UndoReport } | null>(null);
  const [undone, setUndone] = useState<string[]>([]);
  const date = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone });
  const total = (counts: Record<string, number>) => Object.values(counts).reduce((sum, n) => sum + n, 0);

  return (
    <section aria-labelledby="batches-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="batches-heading" className="text-lg font-semibold">{t("undo.title")}</h2>
        <p className="text-sm text-muted">{t("undo.hint")}</p>
      </div>
      <ul className="flex flex-col gap-3">
        {batches.filter((b) => !undone.includes(b.id)).map((batch) => (
          <li key={batch.id} className="flex flex-col gap-2 rounded-xl border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{t("undo.batch", { date: date.format(new Date(batch.created_at)), count: total(batch.counts) })}</span>
              {batch.can_undo ? (
                <button
                  type="button"
                  className="btn-secondary px-3 py-1.5"
                  disabled={pending}
                  onClick={() =>
                    startTransition(async () => {
                      const result = await undoBatch(batch.id, includeEdited, false);
                      if (result.data) setPreview({ id: batch.id, report: result.data });
                      else onError(result.error);
                    })
                  }
                >
                  {t("undo.preview")}
                </button>
              ) : (
                <span className="text-sm text-muted">{t("undo.closed")}</span>
              )}
            </div>
            <p className="text-sm text-muted">{t("undo.until", { date: date.format(new Date(batch.undo_until)) })}</p>
            {preview?.id === batch.id && (
              <div className="flex flex-col gap-2 text-sm">
                <p>
                  {t("undo.removes", { count: total(preview.report.removed) })}
                  {total(preview.report.kept) > 0 && <> {t("undo.keeps", { count: total(preview.report.kept) })}</>}
                </p>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeEdited}
                    onChange={async (event) => {
                      setIncludeEdited(event.target.checked);
                      const result = await undoBatch(batch.id, event.target.checked, false);
                      if (result.data) setPreview({ id: batch.id, report: result.data });
                    }}
                  />
                  {t("undo.includeEdited")}
                </label>
                <div>
                  <button
                    type="button"
                    className="btn-primary px-3 py-1.5"
                    disabled={pending || total(preview.report.removed) === 0}
                    onClick={() =>
                      startTransition(async () => {
                        const result = await undoBatch(batch.id, includeEdited, true);
                        if (!result.data) return onError(result.error);
                        // Edited records that stayed keep the batch open for a second round.
                        if (total(result.data.kept) === 0) setUndone((current) => [...current, batch.id]);
                        setPreview(null);
                      })
                    }
                  >
                    {t("undo.confirm")}
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
