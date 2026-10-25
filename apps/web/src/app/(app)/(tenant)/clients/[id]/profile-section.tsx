import { NotebookPen, Trash2 } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { businessTerms } from "@/lib/verticals";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { deleteNote } from "./profile-actions";
import { NoteForm, ProfileForm } from "./profile-forms";
import { Card } from "@/components/ui/card";
import { IconButton } from "@/components/ui/button";

type Context = Awaited<ReturnType<typeof getTenant>>;
type Props = {
  clientId: string;
  values: Record<string, string | number>;
  context: Context;
  locked: boolean;
};

/** The industry's extra details about the client (e.g. a garage: the car). */
export async function ProfileSection({ clientId, values, context, locked }: Props) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const fields = unwrap(await api.GET("/clients/fields", { params: scope }));
  if (fields.length === 0) return null;
  return (
    <Card as="section" aria-labelledby="profile-heading">
      <h2 id="profile-heading" className="mb-4 text-lg font-semibold">
        {businessTerms(t, tenant, locale)("profile")}
      </h2>
      <ProfileForm
        clientId={clientId}
        fields={fields}
        values={values}
        readOnly={locked || !canWriteClients(tenant)}
      />
    </Card>
  );
}

type NotesProps = {
  clientId: string;
  bookings: { id: string; service_name: string; starts_at: string; status: string }[];
  context: Context;
  locked: boolean;
};

/** The client's latest visits (newest first) that a note can be about. */
function pastVisits<T extends { starts_at: string; status: string }>(bookings: T[]): T[] {
  const now = Date.now();
  return bookings.filter((b) => Date.parse(b.starts_at) <= now && b.status !== "cancelled").slice(0, 10);
}

/** Visit notes: what staff did or noticed at each visit. */
export async function NotesSection({ clientId, bookings, context, locked }: NotesProps) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, me, api, scope } = context;
  const notes = unwrap(await api.GET("/clients/{client_id}/notes", { params: { ...scope, path: { client_id: clientId } } }));
  const canWrite = !locked && (canWriteClients(tenant) || tenant.permissions.includes("bookings.manage"));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone });
  const recentVisits = pastVisits(bookings).map((b) => ({
    id: b.id,
    label: `${b.service_name} · ${day.format(new Date(b.starts_at))}`,
  }));

  return (
    <Card as="section" aria-labelledby="notes-heading" className="flex flex-col gap-4">
      <h2 id="notes-heading" className="flex items-center gap-2 text-lg font-semibold">
        <NotebookPen aria-hidden="true" className="size-5 text-primary-ink" />
        {businessTerms(t, tenant, locale)("visitNotes")}
      </h2>
      {canWrite && <NoteForm clientId={clientId} bookings={recentVisits} />}
      {notes.length === 0 ? (
        <p className="text-sm text-muted">{t("visitNotes.none")}</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {notes.map((note) => {
            const mine = note.author_user_id === me.id;
            return (
              <li key={note.id} className="flex flex-col gap-1 rounded-xl border border-border p-3">
                <p dir="auto" className="whitespace-pre-line text-sm">{note.body}</p>
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                  <span>
                    <time dateTime={note.created_at}>{when.format(new Date(note.created_at))}</time>
                    {note.author_name && ` · ${note.author_name}`}
                    {note.service_name && note.session_starts_at && ` · ${note.service_name} (${day.format(new Date(note.session_starts_at))})`}
                  </span>
                  {canWrite && (mine || canWriteClients(tenant)) && (
                    <form action={deleteNote.bind(null, clientId, note.id)}>
                      <IconButton type="submit" label={t("visitNotes.delete")} className="hover:text-danger">
                        <Trash2 aria-hidden="true" className="size-4" />
                      </IconButton>
                    </form>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
