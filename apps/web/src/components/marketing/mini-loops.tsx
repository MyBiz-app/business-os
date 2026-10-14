/** Tiny looping product visuals for the home page feature cards. Decorative (aria-hidden), pure CSS
 * motion, and they hold still for reduced motion. */
export function MiniLoop({ kind }: { kind: "schedule" | "ai" | "clients" | "app" | "reports" }) {
  return (
    <div aria-hidden="true" className="mt-auto flex h-16 items-end gap-2 rounded-xl bg-foreground/[0.03] p-3 ring-1 ring-border/60">
      {kind === "schedule" &&
        [["w-1/3", "bg-primary"], ["w-1/2", "bg-ai"], ["w-1/4", "bg-electric"]].map(([w, c], i) => (
          <span key={i} className={`loop-slide h-full rounded-md ${w} ${c}`} style={{ animationDelay: `${i * 0.5}s` }} />
        ))}
      {kind === "ai" && (
        <div className="flex w-full items-center gap-2">
          <span className="rounded-full bg-ai px-3 py-1">
            <span className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span key={i} className="loop-dot size-1.5 rounded-full bg-white" style={{ animationDelay: `${i * 0.18}s` }} />
              ))}
            </span>
          </span>
          <span className="h-2 w-1/3 rounded-full bg-foreground/10" />
        </div>
      )}
      {kind === "clients" &&
        ["bg-primary", "bg-ai", "bg-electric", "bg-success"].map((c, i) => (
          <span key={c} className={`es-pulse size-8 rounded-full ${c} ring-2 ring-surface ${i ? "-ms-4" : ""}`} style={{ animationDelay: `${i * 0.35}s` }} />
        ))}
      {kind === "app" && (
        <div className="flex h-full w-full items-center gap-3">
          <span className="es-pulse h-full w-8 rounded-md bg-primary" />
          <span className="flex flex-1 flex-col gap-1.5">
            <span className="h-2 w-full rounded-full bg-foreground/10" />
            <span className="h-2 w-2/3 rounded-full bg-foreground/10" />
          </span>
        </div>
      )}
      {kind === "reports" &&
        [40, 65, 50, 85, 70].map((h, i) => (
          <span key={i} className="loop-bar w-full rounded-t-md bg-gradient-to-t from-primary to-electric" style={{ height: `${h}%`, animationDelay: `${i * 0.15}s` }} />
        ))}
    </div>
  );
}
