"use client";

import { useEffect, useRef, useState } from "react";

type Labels = { site: string; crm: string; name: string; phone: string; send: string; sent: string; lead: string; source: string; fromSite: string; person: string; phoneValue: string };

/** A client fills in the form on a website and the enquiry lands in the CRM as a lead. It plays
 * once when it scrolls into view (and at once for reduced motion). */
export function WebsiteLeadDemo({ labels }: { labels: Labels }) {
  const root = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const play = () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return setStep(3);
      setStep(1);
      timers.push(setTimeout(() => setStep(2), 1400), setTimeout(() => setStep(3), 2600));
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        observer.disconnect();
        play();
      },
      { threshold: 0.4 },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <div ref={root} aria-hidden="true" className="grid items-stretch gap-6 md:grid-cols-[1fr_auto_1fr]">
      <div className="card flex flex-col gap-3 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{labels.site}</p>
        <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm">
          {labels.name}: <bdi className={step >= 1 ? "font-semibold" : "text-muted"}>{step >= 1 ? labels.person : "..."}</bdi>
        </div>
        <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm">
          {labels.phone}: <bdi className={step >= 1 ? "font-semibold" : "text-muted"} dir="ltr">{step >= 1 ? labels.phoneValue : "..."}</bdi>
        </div>
        <span className={`rounded-full px-5 py-2 text-center text-sm font-bold ${step >= 2 ? "bg-success text-on-primary" : "bg-primary text-on-primary"}`}>
          {step >= 2 ? labels.sent : labels.send}
        </span>
      </div>
      <div className="flex items-center justify-center text-2xl text-primary-ink rtl:rotate-180">
        <span className={step >= 2 ? "mk-rise" : "opacity-30"}>{"→"}</span>
      </div>
      <div className="card flex flex-col gap-3 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{labels.crm}</p>
        {step >= 3 ? (
          <div className="mk-rise flex flex-col gap-1 rounded-xl border border-primary/40 bg-primary/10 p-4">
            <p className="text-xs font-bold text-primary-ink">{labels.lead}</p>
            <p className="font-semibold">{labels.person}</p>
            <p className="text-sm text-muted">
              {labels.source}: {labels.fromSite}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted">{"..."}</div>
        )}
      </div>
    </div>
  );
}
