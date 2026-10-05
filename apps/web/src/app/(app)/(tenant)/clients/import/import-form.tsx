"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useId, useState, useTransition } from "react";

import { FileField } from "@/components/form/file-field";

import { runImport, type ImportField, type ImportResult, type ImportState } from "./actions";

const FIELDS: ImportField[] = [
  "first_name",
  "last_name",
  "full_name",
  "email",
  "phone",
  "date_of_birth",
  "notes",
  "status",
];
const SOURCES = ["walk_in", "referral", "instagram", "facebook", "google", "website", "app", "other"] as const;
const CONTROL =
  "w-full min-w-0 control px-3 py-2";

/** Upload a file, check how its columns map, preview, then import. */
export function ImportForm() {
  const t = useTranslations("clientImport");
  const tClients = useTranslations("clients");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<ImportState["error"]>();
  const [source, setSource] = useState("");
  const [pending, startTransition] = useTransition();
  const sourceId = useId();

  const send = (target: File, mapping: ImportResult["mapping"] | null, commit: boolean) =>
    startTransition(async () => {
      const data = new FormData();
      data.set("file", target);
      if (mapping) data.set("mapping", JSON.stringify(mapping));
      data.set("commit", String(commit));
      if (commit && source) data.set("source", source);
      const state = await runImport(data);
      setError(state.error);
      setResult(state.result ?? null);
    });

  const choose = (chosen: File | null) => {
    setFile(chosen);
    setResult(null);
    setError(undefined);
    if (chosen) send(chosen, null, false);
  };

  const remap = (column: number, value: string) => {
    if (!file || !result) return;
    const target = (value || null) as ImportField | null;
    // A field can feed only one column: picking it here clears it elsewhere.
    const mapping = result.mapping.map((current, i) =>
      i === column ? target : current === target ? null : current,
    );
    send(file, mapping, false);
  };

  if (result?.imported) {
    return (
      <div role="status" className="flex flex-col gap-3 card p-6">
        <p className="text-lg font-semibold">{t("done", { count: result.ready })}</p>
        {result.duplicates + result.invalid > 0 && (
          <p className="text-sm text-muted">{t("doneSkipped", { count: result.duplicates + result.invalid })}</p>
        )}
        <div className="flex flex-wrap gap-4">
          <Link href="/clients" className="text-primary underline-offset-4 hover:underline">
            {t("viewClients")}
          </Link>
          <button
            type="button"
            onClick={() => choose(null)}
            className="text-primary underline-offset-4 hover:underline"
          >
            {t("importMore")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3 card p-6">
        <FileField
          label={t("file")}
          hint={t("fileHint")}
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        {pending && (
          <p role="status" className="text-sm text-muted">
            {t("working")}
          </p>
        )}
        {error && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {t(`errors.${error}`)}
          </p>
        )}
      </section>

      {result && file && (
        <>
          <section aria-labelledby="columns-heading" className="flex flex-col gap-4 card p-6">
            <div className="flex flex-col gap-1">
              <h2 id="columns-heading" className="text-lg font-semibold">
                {t("columns")}
              </h2>
              <p className="text-sm text-muted">{t("columnsHint")}</p>
            </div>
            <ul className="flex flex-col divide-y divide-border">
              {result.columns.map((column, i) => (
                <li key={i} className="grid gap-2 py-3 sm:grid-cols-2 sm:items-center">
                  <div className="flex min-w-0 flex-col">
                    <span className="font-medium" dir="auto">
                      {column || t("noHeader", { number: i + 1 })}
                    </span>
                    {result.examples[i] && (
                      <span className="truncate text-sm text-muted" dir="auto">
                        {t("example", { value: result.examples[i] })}
                      </span>
                    )}
                  </div>
                  <select
                    aria-label={t("fieldFor", { column: column || t("noHeader", { number: i + 1 }) })}
                    value={result.mapping[i] ?? ""}
                    disabled={pending}
                    onChange={(event) => remap(i, event.target.value)}
                    className={CONTROL}
                  >
                    <option value="">{t("ignore")}</option>
                    {FIELDS.map((target) => (
                      <option key={target} value={target}>
                        {t(`fields.${target}`)}
                      </option>
                    ))}
                  </select>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="preview-heading" className="flex flex-col gap-4 card p-6">
            <h2 id="preview-heading" className="text-lg font-semibold">
              {t("preview")}
            </h2>
            <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
              <li>{t("rows", { count: result.rows })}</li>
              <li className="font-semibold">{t("ready", { count: result.ready })}</li>
              <li>{t("duplicates", { count: result.duplicates })}</li>
              <li>{t("invalid", { count: result.invalid })}</li>
            </ul>
            {result.sample.length > 0 && (
              <div className="flex flex-col gap-1">
                <h3 className="font-semibold">{t("sample")}</h3>
                <ul className="text-sm" dir="auto">
                  {result.sample.map((client, i) => (
                    <li key={i}>
                      {[client.first_name, client.last_name].filter(Boolean).join(" ")}
                      {(client.phone || client.email) && (
                        <span className="text-muted"> · {[client.phone, client.email].filter(Boolean).join(" · ")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.issues.length > 0 && (
              <div className="flex flex-col gap-1">
                <h3 className="font-semibold">{t("issues")}</h3>
                <ul className="text-sm text-muted">
                  {result.issues.map((issue, i) => (
                    <li key={i}>{t("issue", { line: issue.line, problem: t(`problems.${issue.code}`) })}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex max-w-sm flex-col gap-1.5">
              <label htmlFor={sourceId} className="text-sm font-medium">
                {t("source")}
              </label>
              <select id={sourceId} value={source} onChange={(event) => setSource(event.target.value)} className={CONTROL}>
                <option value="">{t("sourceNone")}</option>
                {SOURCES.map((value) => (
                  <option key={value} value={value}>
                    {tClients(`sources.${value}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <button
                type="button"
                disabled={pending || result.ready === 0}
                aria-busy={pending}
                onClick={() => send(file, result.mapping, true)}
                className="btn-primary px-4 py-2.5"
              >
                {t("import", { count: result.ready })}
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
