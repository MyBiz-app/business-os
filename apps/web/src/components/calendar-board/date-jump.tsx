"use client";

import { useRouter } from "next/navigation";

/** Jump to any date: a native date picker that opens the board there. `href` has `__day__` for the date. */
export function DateJump({ value, href, label }: { value: string; href: string; label: string }) {
  const router = useRouter();
  return (
    <input
      type="date"
      aria-label={label}
      title={label}
      value={value}
      onChange={(event) => {
        if (event.target.value) router.push(href.replace("__day__", event.target.value));
      }}
      className="control h-9 w-auto px-2 py-1 text-sm"
    />
  );
}
