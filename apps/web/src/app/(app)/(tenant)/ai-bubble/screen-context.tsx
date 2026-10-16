"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

type Value = { label: string | null; setLabel: (label: string | null) => void };

const ScreenContext = createContext<Value>({ label: null, setLabel: () => {} });

/** Holds what the open screen is about ("Client: Dana Cohen"), for the floating AI bubble to pass on. */
export function ScreenContextProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null);
  const value = useMemo(() => ({ label, setLabel }), [label]);
  return <ScreenContext.Provider value={value}>{children}</ScreenContext.Provider>;
}

export const useScreenLabel = () => useContext(ScreenContext).label;

/** A screen renders this to tell the AI bubble what it shows. Renders nothing. */
export function AiScreen({ label }: { label: string }) {
  const { setLabel } = useContext(ScreenContext);
  useEffect(() => {
    setLabel(label);
    return () => setLabel(null);
  }, [label, setLabel]);
  return null;
}
