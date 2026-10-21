"use client";

import { ChevronDown } from "lucide-react";
import { type ReactNode, useId } from "react";

import type { SelectOption } from "@/components/form/field";
import { inputDir } from "@/lib/bidi";

/** A grouped list, like the iPhone's Settings: rows in one card, a hairline between them. */
export function SettingsRows({ children }: { children: ReactNode }) {
  return <div className="-my-1 flex flex-col divide-y divide-border">{children}</div>;
}

/** One row: the label and its help on the start side, the control on the end side. On a narrow
 * screen the control drops under the label, full width. */
function Row({ label, hint, id, children, inline = false }: { label: string; hint?: string; id: string; children: ReactNode; inline?: boolean }) {
  return (
    <div className={`flex gap-x-6 gap-y-2 py-3.5 ${inline ? "items-center justify-between" : "flex-col @xl:flex-row @xl:items-center @xl:justify-between"}`}>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint && (
          <p id={`${id}-hint`} className="max-w-[36rem] text-xs text-muted text-pretty">
            {hint}
          </p>
        )}
      </div>
      <div className={inline ? "shrink-0" : "w-full @xl:w-72 @xl:shrink-0"}>{children}</div>
    </div>
  );
}

type InputRowProps = React.InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string };

export function InputRow({ label, hint, ...inputProps }: InputRowProps) {
  const id = useId();
  return (
    <Row label={label} hint={hint} id={id}>
      <input id={id} aria-describedby={hint ? `${id}-hint` : undefined} className="control w-full min-w-0 px-3 py-2" dir={inputDir(inputProps.type)} {...inputProps} />
    </Row>
  );
}

type SelectRowProps = React.SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: string; options: SelectOption[] };

export function SelectRow({ label, hint, options, ...selectProps }: SelectRowProps) {
  const id = useId();
  return (
    <Row label={label} hint={hint} id={id}>
      <div className="relative">
        <select id={id} aria-describedby={hint ? `${id}-hint` : undefined} className="control w-full min-w-0 appearance-none px-3 py-2 pe-9" {...selectProps}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden="true" className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      </div>
    </Row>
  );
}

type SwitchRowProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string; hint?: string };

/** An on/off row with a switch at the end. Still a checkbox underneath: it submits with the form. */
export function SwitchRow({ label, hint, className = "", ...inputProps }: SwitchRowProps) {
  const id = useId();
  return (
    <Row label={label} hint={hint} id={id} inline>
      <input
        id={id}
        type="checkbox"
        role="switch"
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={`relative h-7 w-12 shrink-0 cursor-pointer appearance-none rounded-full bg-foreground/20 transition-colors duration-200 checked:bg-primary after:absolute after:start-0.5 after:top-0.5 after:size-6 after:rounded-full after:bg-white after:shadow-sm after:transition-transform after:duration-200 checked:after:translate-x-5 rtl:checked:after:-translate-x-5 motion-reduce:transition-none motion-reduce:after:transition-none ${className}`}
        {...inputProps}
      />
    </Row>
  );
}
