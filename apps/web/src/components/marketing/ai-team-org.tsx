"use client";

import { useTranslations } from "next-intl";
import Image from "next/image";
import { useState } from "react";

import { Reveal } from "@/components/marketing/reveal";
import { BRANCH_PORTRAITS, CHIEF, PORTRAITS, SPECIALISTS, type TeamKey } from "@/lib/ai-team";

function Face({ agent, size }: { agent: TeamKey; size: "lg" | "md" }) {
  const t = useTranslations("marketing.aiTeam.agents");
  const px = size === "lg" ? 96 : 64;
  return (
    <figure className="flex flex-col items-center gap-2 text-center">
      <Image src={PORTRAITS[agent]} alt="" width={px} height={px} className={`rounded-full object-cover shadow-lg ring-2 ring-border ${size === "lg" ? "size-24" : "size-16"}`} />
      <figcaption className="flex flex-col">
        <span className="font-bold">{t(`${agent}.name`)}</span>
        <span className="text-xs text-muted">{t(`${agent}.role`)}</span>
      </figcaption>
    </figure>
  );
}

const LINK = <span aria-hidden="true" className="mx-auto block h-6 w-px bg-border" />;

/** The AI team as an org chart: the chief of staff on top and a specialist per field below. The
 * "network" view adds a manager agent for every branch between them. */
export function TeamOrg() {
  const t = useTranslations("marketing.aiTeam.org");
  const [network, setNetwork] = useState(false);
  const branches = t.raw("branches") as { city: string; name: string }[];

  return (
    <div className="flex flex-col items-center gap-8">
      <div role="group" aria-label={t("modeLabel")} className="flex gap-2">
        {[false, true].map((value) => (
          <button
            key={String(value)}
            type="button"
            aria-pressed={network === value}
            onClick={() => setNetwork(value)}
            className="btn-plain h-10 rounded-full border border-border bg-surface px-5 text-sm font-semibold transition-colors hover:border-primary aria-pressed:border-primary aria-pressed:text-primary-ink"
          >
            {value ? t("network") : t("single")}
          </button>
        ))}
      </div>

      <section aria-label={t("label")} className="flex w-full flex-col gap-0">
        <Reveal>
          <Face agent={CHIEF} size="lg" />
        </Reveal>
        <p className="mx-auto mt-3 max-w-md text-center text-sm text-muted">{t("chiefNote")}</p>
        {LINK}
        {network && (
          <>
            <div className="mx-auto w-full max-w-3xl rounded-3xl border border-ai/25 bg-ai/[0.06] p-5">
              <p className="mb-1 text-center font-bold">{t("branchesTitle")}</p>
              <p className="mb-5 text-center text-sm text-muted">{t("branchesNote")}</p>
              <ul className="grid gap-4 sm:grid-cols-3">
                {branches.map((branch, index) => (
                  <li key={branch.city} className="mk-rise flex flex-col items-center gap-2 rounded-2xl bg-surface p-4 shadow-sm ring-1 ring-border" style={{ animationDelay: `${index * 120}ms` }}>
                    <Image src={BRANCH_PORTRAITS[index]!} alt="" width={64} height={64} className="size-16 rounded-full object-cover ring-2 ring-border" />
                    <p className="font-bold">{branch.name}</p>
                    <p className="text-xs text-muted">{t("branchManager")} · {branch.city}</p>
                  </li>
                ))}
              </ul>
            </div>
            {LINK}
          </>
        )}
        <ul className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-4">
          {SPECIALISTS.map((agent, index) => (
            <li key={agent}>
              <Reveal delay={index * 60}>
                <Face agent={agent} size="md" />
              </Reveal>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
