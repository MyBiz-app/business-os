"use client";

import { useRouter } from "next/navigation";

import { type Away, type BoardPerson, type BoardStation, type BoardTemplate, type Editing, ShiftDialog } from "./shift-board";

/** Opens a shift's editor (or the form for a new one) from a link (`?edit=<id>`, `?add=<day>:<branch>`),
 * so a block in the time grid or the by-branch roster is editable. */
export function EditFromUrl({ editing, people, branches, templates, stations, closeHref, away }: { editing: Editing; people: BoardPerson[]; branches: { id: string; name: string; color: string }[]; templates: BoardTemplate[]; stations: BoardStation[]; closeHref: string; away?: Away }) {
  const router = useRouter();
  return <ShiftDialog editing={editing} people={people} branches={branches} templates={templates} stations={stations} onClose={() => router.replace(closeHref, { scroll: false })} away={away} />;
}
