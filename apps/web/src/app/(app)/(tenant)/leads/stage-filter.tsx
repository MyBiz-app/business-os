"use client";

import { Check, ChevronDown, Columns3 } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDismiss } from "@/components/use-dismiss";

type Props = {
  stages: { value: string; label: string }[];
  selected: string[];
  label: string;
  allLabel: string;
  countLabel: string;
};

/** A dropdown of checkboxes choosing which pipeline columns to show. It lives inside the filter
 * form, so the chosen stages are submitted with it as repeated `stage` values. */
export function StageFilter({ stages, selected, label, allLabel, countLabel }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);

  const summary = selected.length === stages.length ? allLabel : countLabel;
  return (
    <div ref={root} className="relative flex flex-col gap-1.5 text-sm font-medium">
      <span id={`${panelId}-label`}>{label}</span>
      <Button
        ref={button}
        variant="plain"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        aria-labelledby={`${panelId}-label ${panelId}-value`}
        onClick={() => setOpen((value) => !value)}
        className="control flex min-w-44 items-center justify-between gap-2 px-3 py-2 font-normal"
      >
        <span id={`${panelId}-value`} className="flex items-center gap-2">
          <Columns3 aria-hidden="true" className="size-4 text-muted" />
          {summary}
        </span>
        <ChevronDown aria-hidden="true" className="size-4 text-muted" />
      </Button>
      <fieldset
        id={panelId}
        data-open={open}
        className="popover absolute start-0 top-full z-30 mt-2 flex w-56 max-w-[calc(100vw-2rem)] origin-top flex-col gap-0.5 p-1.5"
      >
        <legend className="sr-only">{label}</legend>
        {stages.map(({ value, label: text }) => (
          <label
            key={value}
            className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-normal transition-colors hover:bg-subtle has-[:focus-visible]:bg-subtle"
          >
            <input type="checkbox" name="stage" value={value} defaultChecked={selected.includes(value)} className="peer sr-only" />
            <span
              aria-hidden="true"
              className="grid size-4 place-items-center rounded border border-border text-transparent peer-checked:border-primary peer-checked:bg-primary peer-checked:text-on-primary"
            >
              <Check className="size-3" />
            </span>
            {text}
          </label>
        ))}
      </fieldset>
    </div>
  );
}
