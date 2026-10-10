"use client";

import { useRouter } from "next/navigation";

import { type Away, type BoardPerson, type Editing, ShiftDialog } from "./shift-board";

/** Opens a shift's editor (or the form for a new one) from a link (`?edit=<id>`, `?add=<day>:<branch>`),
 * so a block in the time grid or the by-branch roster is editable. */
export function EditFromUrl({ editing, people, branches, closeHref, away }: { editing: Editing; people: BoardPerson[]; branches: { id: string; name: string; color: string }[]; closeHref: string; away?: Away }) {
  const router = useRouter();
  return <ShiftDialog editing={editing} people={people} branches={branches} onClose={() => router.replace(closeHref, { scroll: false })} away={away} />;
}
