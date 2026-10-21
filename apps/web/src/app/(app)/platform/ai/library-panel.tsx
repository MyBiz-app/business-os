"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, useTransition } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";

import type { ChatRole } from "./actions";
import {
  deleteLibraryDocument,
  libraryVersions,
  listLibrary,
  openLibraryDocument,
  refreshLibrarySources,
  restoreLibraryVersion,
  saveLibraryDocument,
  searchLibrary,
  setLibraryDocumentEnabled,
  uploadLibraryFile,
  type LibraryChange,
  type LibraryDocument,
  type LibraryDocumentBody,
  type LibraryHit,
  type LibraryVersion,
} from "./library-actions";

type Mode = "note" | "summary" | "link" | "file";
const COUNTRIES = ["il", "us", "eu", "all"] as const;

/** One agent's library: documents, files and notes it can search, with versions. Everyone on the team reads it; changing needs billing.manage. */
export function LibraryPanel({ agent, canEdit }: { agent: ChatRole; canEdit: boolean }) {
  const t = useTranslations("platform.ai.library");
  const locale = useLocale();
  const [docs, setDocs] = useState<LibraryDocument[] | null>(null);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [adding, setAdding] = useState<Mode | null>(null);
  const [editing, setEditing] = useState<LibraryDocumentBody | null>(null);
  const [history, setHistory] = useState<{ doc: LibraryDocument; versions: LibraryVersion[] } | null>(null);
  const [pending, start] = useTransition();
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  const [loaded, setLoaded] = useState(0);
  const reload = () => setLoaded((n) => n + 1);

  // The parent keys this panel by agent, so a new agent starts with fresh state.
  useEffect(() => {
    let current = true;
    void listLibrary(agent).then((result) => {
      if (!current) return;
      if (result.data) setDocs(result.data);
      else setError(result.error);
    });
    return () => {
      current = false;
    };
  }, [agent, loaded]);

  const run = (job: () => Promise<{ error?: string }>, done?: string) =>
    start(async () => {
      setError(undefined);
      setNotice(undefined);
      const result = await job();
      if (result.error) setError(result.error);
      else if (done) setNotice(done);
      reload();
    });

  const readSources = () =>
    start(async () => {
      setError(undefined);
      const counts = { updated: 0, unchanged: 0, failed: 0 };
      let offset = 0;
      for (;;) {
        const { data, error: failed } = await refreshLibrarySources(agent, offset);
        if (!data) {
          setError(failed);
          break;
        }
        for (const r of data.results) counts[r.result] += 1;
        offset += data.results.length;
        setNotice(t("reading", { done: offset, remaining: data.remaining }));
        if (data.remaining === 0 || data.results.length === 0) break;
      }
      setNotice(t("readDone", counts));
      reload();
    });

  const openHistory = (doc: LibraryDocument) =>
    start(async () => {
      const result = await libraryVersions(doc.id);
      if (result.data) setHistory({ doc, versions: result.data });
      else setError(result.error);
    });

  const edit = (doc: LibraryDocument) =>
    start(async () => {
      const result = await openLibraryDocument(doc.id);
      if (result.data) {
        setEditing(result.data);
        setAdding(null);
      } else setError(result.error);
    });

  const status = (doc: LibraryDocument) => (doc.chunks === 0 ? t("noText") : t("pieces", { count: doc.chunks }));

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t("hint")}</p>
      <FormError message={error ? t(`errors.${error}` as "errors.generic") : undefined} />
      <FormNotice message={notice} />

      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          {(["note", "summary", "link", "file"] as const).map((mode) => (
            <button key={mode} type="button" onClick={() => { setAdding(mode); setEditing(null); }} className="btn-secondary px-3 py-1.5 text-sm" aria-pressed={adding === mode}>
              {t(`add.${mode}`)}
            </button>
          ))}
          <button type="button" onClick={readSources} disabled={pending} className="btn-secondary px-3 py-1.5 text-sm">
            {t("readSources")}
          </button>
        </div>
      )}

      {adding && (
        <DocumentForm
          key={adding}
          mode={adding}
          disabled={pending}
          onCancel={() => setAdding(null)}
          onSave={(form) =>
            run(async () => {
              const result = adding === "file" ? await uploadLibraryFile(agent, form.file!) : await saveLibraryDocument(agent, null, form.change!);
              if (!result.error) setAdding(null);
              return result;
            }, t("saved"))
          }
        />
      )}
      {editing && (
        <DocumentForm
          key={editing.id}
          mode={editing.kind}
          existing={editing}
          disabled={pending}
          onCancel={() => setEditing(null)}
          onSave={(form) =>
            run(async () => {
              const result = await saveLibraryDocument(agent, editing.id, form.change!);
              if (!result.error) setEditing(null);
              return result;
            }, t("saved"))
          }
        />
      )}

      {docs === null ? (
        <p className="text-sm text-muted">{t("loading")}</p>
      ) : docs.length === 0 ? (
        <p className="card p-4 text-sm text-muted">{t("empty")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {docs.map((doc) => (
            <li key={doc.id} className={`card flex flex-col gap-2 p-3 ${doc.enabled ? "" : "opacity-60"}`}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-medium" dir="auto">{doc.title}</span>
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs">{t(`kind.${doc.kind}`)}</span>
                {doc.country && <span className="text-xs text-muted">{t(`country.${doc.country}`)}</span>}
                {!doc.enabled && <span className="text-xs text-danger">{t("off")}</span>}
              </div>
              <p className="text-xs text-muted" dir="auto">
                {[doc.source_org, status(doc), t("version", { n: doc.version }), doc.reviewed_on ? t("reviewed", { date: day.format(new Date(doc.reviewed_on)) }) : t("neverReviewed")].filter(Boolean).join(" · ")}
              </p>
              {doc.source_url && (
                <a href={doc.source_url} target="_blank" rel="noopener noreferrer" dir="ltr" className="truncate text-xs underline">{doc.source_url}</a>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => openHistory(doc)} disabled={pending} className="btn-plain text-sm underline">{t("history")}</button>
                {canEdit && (
                  <>
                    <button type="button" onClick={() => edit(doc)} disabled={pending} className="btn-plain text-sm underline">{t("edit")}</button>
                    <button type="button" onClick={() => run(() => setLibraryDocumentEnabled(doc.id, !doc.enabled))} disabled={pending} className="btn-plain text-sm underline">
                      {doc.enabled ? t("switchOff") : t("switchOn")}
                    </button>
                    <button
                      type="button"
                      onClick={() => { if (window.confirm(t("confirmDelete", { title: doc.title }))) run(() => deleteLibraryDocument(doc.id)); }}
                      disabled={pending}
                      className="btn-plain text-sm text-danger underline"
                    >
                      {t("delete")}
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {history && (
        <section aria-label={t("history")} className="card flex flex-col gap-2 p-3">
          <h3 className="font-medium" dir="auto">{t("historyOf", { title: history.doc.title })}</h3>
          <ul className="flex flex-col gap-1 text-sm">
            {history.versions.map((v) => (
              <li key={v.version} className="flex flex-wrap items-center gap-2">
                <span>{t("version", { n: v.version })}</span>
                <span className="text-muted">{day.format(new Date(v.created_at))} · {v.created_by}{v.change_note ? ` · ${v.change_note}` : ""}</span>
                {canEdit && v.version !== history.doc.version && (
                  <button
                    type="button"
                    onClick={() => run(async () => { const r = await restoreLibraryVersion(history.doc.id, v.version); if (!r.error) setHistory(null); return r; }, t("restored"))}
                    disabled={pending}
                    className="btn-plain underline"
                  >
                    {t("restore")}
                  </button>
                )}
              </li>
            ))}
          </ul>
          <div><button type="button" onClick={() => setHistory(null)} className="btn-plain text-sm underline">{t("close")}</button></div>
        </section>
      )}

      <SearchCheck agent={agent} />
    </div>
  );
}

type FormValue = { change?: LibraryChange; file?: FormData };

function DocumentForm({ mode, existing, disabled, onSave, onCancel }: { mode: Mode; existing?: LibraryDocumentBody; disabled: boolean; onSave: (value: FormValue) => void; onCancel: () => void }) {
  const t = useTranslations("platform.ai.library");
  // A link has no text of its own until its source is read; every other kind shows its text.
  const hasBody = mode === "note" || mode === "summary" || (existing !== undefined && (mode === "file" || existing.body !== null));
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const text = (name: string) => String(data.get(name) ?? "").trim() || null;
        if (mode === "file" && !existing) {
          onSave({ file: data });
          return;
        }
        onSave({
          change: {
            kind: mode,
            title: text("title") ?? "",
            body: mode === "link" && !existing?.body ? null : text("body"),
            source_url: text("source_url"),
            source_org: text("source_org"),
            country: text("country") as LibraryChange["country"],
            reviewed_on: text("reviewed_on"),
            enabled: existing?.enabled ?? true,
            change_note: text("change_note"),
          },
        });
      }}
      className="card flex flex-col gap-3 p-4"
    >
      <h3 className="font-medium">{existing ? t("editing") : t(`add.${mode}`)}</h3>
      {mode === "file" && !existing && (
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("fields.file")}
          <input name="file" type="file" required accept=".txt,.md,.markdown,.html,.htm,.docx,.pdf" className="font-normal" />
          <span className="text-xs font-normal text-muted">{t("fields.fileHint")}</span>
        </label>
      )}
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        {t("fields.title")}
        <input name="title" defaultValue={existing?.title ?? ""} required={mode !== "file"} maxLength={200} dir="auto" className="control px-3 py-2 font-normal" />
      </label>
      {hasBody && (
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("fields.body")}
          <textarea name="body" defaultValue={existing?.body ?? ""} required={mode === "note" || mode === "summary"} rows={8} dir="auto" className="control px-3 py-2 font-normal" />
          <span className="text-xs font-normal text-muted">{t(mode === "summary" ? "fields.summaryHint" : mode === "note" ? "fields.noteHint" : "fields.bodyHint")}</span>
        </label>
      )}
      {mode !== "note" && mode !== "summary" && (
        <>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            {t("fields.url")}
            <input name="source_url" type="url" defaultValue={existing?.source_url ?? ""} required={mode === "link"} pattern="https?://.*" dir="ltr" placeholder="https://" className="control px-3 py-2 font-normal" />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("fields.org")}
              <input name="source_org" defaultValue={existing?.source_org ?? ""} maxLength={200} dir="auto" className="control px-3 py-2 font-normal" />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              {t("fields.country")}
              <select name="country" defaultValue={existing?.country ?? ""} className="control px-3 py-2 font-normal">
                <option value="">-</option>
                {COUNTRIES.map((c) => <option key={c} value={c}>{t(`country.${c}`)}</option>)}
              </select>
            </label>
            {existing && (
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                {t("fields.reviewed")}
                <input name="reviewed_on" type="date" defaultValue={existing.reviewed_on ?? ""} className="control px-3 py-2 font-normal" />
              </label>
            )}
          </div>
        </>
      )}
      {existing && (
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          {t("fields.changeNote")}
          <input name="change_note" maxLength={300} dir="auto" className="control px-3 py-2 font-normal" />
        </label>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={disabled} className="btn-primary px-4 py-2">{t("save")}</button>
        <button type="button" onClick={onCancel} className="btn-secondary px-4 py-2">{t("cancel")}</button>
      </div>
    </form>
  );
}

/** Lets the team ask the library a question and see which pieces the agent would be given. */
function SearchCheck({ agent }: { agent: ChatRole }) {
  const t = useTranslations("platform.ai.library");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<LibraryHit[] | null>(null);
  const [pending, start] = useTransition();
  return (
    <section aria-label={t("tryTitle")} className="flex flex-col gap-2">
      <h3 className="font-medium">{t("tryTitle")}</h3>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!q.trim()) return;
          start(async () => setHits((await searchLibrary(agent, q.trim())).data ?? []));
        }}
        className="flex gap-2"
      >
        <label htmlFor={`library-q-${agent}`} className="sr-only">{t("tryTitle")}</label>
        <input id={`library-q-${agent}`} value={q} onChange={(event) => setQ(event.target.value)} maxLength={300} dir="auto" placeholder={t("tryPlaceholder")} className="control min-w-0 flex-1 px-3 py-2" />
        <button type="submit" disabled={pending || !q.trim()} className="btn-secondary px-4 py-2">{t("try")}</button>
      </form>
      {hits && (hits.length === 0 ? (
        <p className="text-sm text-muted">{t("tryNothing")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {hits.map((hit, index) => (
            <li key={index} className="card p-3 text-sm">
              <p className="font-medium" dir="auto">{hit.document}{hit.section ? ` · ${hit.section}` : ""}</p>
              <p className="mt-1 whitespace-pre-wrap text-muted" dir="auto">{hit.text.length > 400 ? `${hit.text.slice(0, 400)}...` : hit.text}</p>
            </li>
          ))}
        </ul>
      ))}
    </section>
  );
}
