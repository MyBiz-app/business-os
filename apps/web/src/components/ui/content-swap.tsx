"use client";

import { type ReactNode, useEffect, useState } from "react";

const OUT_MS = 100; // matches `.content-swap[data-leaving]` in globals.css

/** Switches content softly when `swapKey` changes: the old content fades out (100ms), the new
 * one fades in with a small slide (150ms). Pair it with `SegmentedControl` for tabs, folders and
 * periods. It never delays an action: the control already moved, only the content catches up. */
export function ContentSwap({ swapKey, children }: { swapKey: string; children: ReactNode }) {
  const [shownKey, setShownKey] = useState(swapKey);
  const [snapshot, setSnapshot] = useState(children);
  const leaving = shownKey !== swapKey;
  // While nothing is leaving, remember what is on screen so it can fade out later.
  if (!leaving && snapshot !== children) setSnapshot(children);

  useEffect(() => {
    if (!leaving) return;
    const id = window.setTimeout(() => setShownKey(swapKey), OUT_MS);
    return () => window.clearTimeout(id);
  }, [leaving, swapKey]);

  return (
    <div key={shownKey} className="content-swap" data-leaving={leaving || undefined}>
      {leaving ? snapshot : children}
    </div>
  );
}
