"use client";

import { useRouter } from "next/navigation";

import { type BoardPerson, type BoardShift, ShiftDialog } from "./shift-board";

/** Opens a shift's editor from a link (`?edit=<id>`), so a block in the time grid is editable. */
export function EditFromUrl({ shift, people, branches, closeHref }: { shift: BoardShift; people: BoardPerson[]; branches: { id: string; name: string; color: string }[]; closeHref: string }) {
  const router = useRouter();
  return <ShiftDialog editing={{ shift, userId: shift.userId, day: shift.day }} people={people} branches={branches} onClose={() => router.replace(closeHref, { scroll: false })} />;
}
