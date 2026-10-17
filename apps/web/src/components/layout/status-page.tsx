import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand-mark";

/** A full-page notice (page not found, something broke) in the marketing style: a soft
 * gradient glow behind the brand mark, a heading, a short text and the actions. */
export function StatusPage({ title, text, detail, children }: { title: string; text: string; detail?: ReactNode; children: ReactNode }) {
  return (
    <main id="main" className="mk relative isolate flex flex-1 flex-col items-center justify-center overflow-hidden bg-background px-4 py-16 text-center text-foreground">
      <div aria-hidden="true" className="pointer-events-none absolute -top-32 start-[15%] -z-10 size-[24rem] rounded-full bg-primary/20 blur-[110px]" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 end-[10%] -z-10 size-[22rem] rounded-full bg-electric/15 blur-[110px]" />
      <div className="enter flex max-w-md flex-col items-center gap-4">
        <BrandMark className="size-16 drop-shadow-lg" />
        <h1 className="text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">{title}</h1>
        <p className="text-lg text-muted text-pretty">{text}</p>
        {detail}
        <div className="mt-2 flex flex-wrap justify-center gap-3">{children}</div>
      </div>
    </main>
  );
}
