"use client";

import { Check, Link2 } from "lucide-react";
import { useState } from "react";

/** A link people can share (e.g. in an Instagram bio), with a copy button. */
export function CopyLink({ link, label, copy, copied }: { link: string; label: string; copy: string; copied: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="flex min-w-0 flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <div className="flex min-w-0 items-center gap-2">
        <a href={link} target="_blank" rel="noreferrer" dir="ltr" className="control truncate px-3 py-2 text-xs text-muted">
          {link}
        </a>
        <button
          type="button"
          onClick={async () => {
            await navigator.clipboard.writeText(link).catch(() => undefined);
            setDone(true);
            setTimeout(() => setDone(false), 2000);
          }}
          className="btn-secondary shrink-0 px-3 py-2"
        >
          {done ? <Check aria-hidden="true" className="size-4" /> : <Link2 aria-hidden="true" className="size-4" />}
          <span aria-live="polite">{done ? copied : copy}</span>
        </button>
      </div>
    </div>
  );
}
