import { AlertCircle, ChevronDown } from "lucide-react";
import { useId } from "react";

import { inputDir } from "@/lib/bidi";

const CONTROL =
  "control w-full min-w-0 px-3 py-2";

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  /** A problem with this field: shown right under it, and the field's edge turns red. */
  error?: string;
};

/** The message under a field that has a problem. */
export function FieldError({ id, message }: { id?: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="field-error flex items-start gap-1.5 text-sm text-danger">
      <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {message}
    </p>
  );
}

export function Field({ label, hint, error, ...inputProps }: FieldProps) {
  const id = useId();
  const hintId = hint && !error ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input id={id} aria-describedby={hintId ?? errorId} aria-invalid={error ? true : undefined} className={CONTROL} dir={inputDir(inputProps.type)} {...inputProps} />
      <FieldError id={errorId} message={error} />
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

type TextAreaFieldProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string };

export function TextAreaField({ label, error, ...textAreaProps }: TextAreaFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <textarea id={id} rows={4} className={CONTROL} dir="auto" aria-invalid={error ? true : undefined} {...textAreaProps} />
      <FieldError message={error} />
    </div>
  );
}

export type SelectOption = { value: string; label: string; /** Options with the same group are listed together under it. */ group?: string };

type SelectFieldProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: SelectOption[];
};

/** Consecutive options of one group, in order. */
function grouped(options: SelectOption[]): { group?: string; options: SelectOption[] }[] {
  const runs: { group?: string; options: SelectOption[] }[] = [];
  for (const option of options) {
    const last = runs.at(-1);
    if (last && last.group === option.group) last.options.push(option);
    else runs.push({ group: option.group, options: [option] });
  }
  return runs;
}

export function SelectField({ label, options, ...selectProps }: SelectFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative">
      <select id={id} className={`${CONTROL} appearance-none pe-9`} {...selectProps}>
        {grouped(options).map(({ group, options: run }) => {
          const items = run.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ));
          return group ? (
            <optgroup key={`${group}:${run[0]!.value}`} label={group}>
              {items}
            </optgroup>
          ) : (
            items
          );
        })}
      </select>
      <ChevronDown aria-hidden="true" className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      </div>
    </div>
  );
}

type CheckboxFieldProps = React.InputHTMLAttributes<HTMLInputElement> & { label: string };

export function CheckboxField({ label, ...inputProps }: CheckboxFieldProps) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <input id={id} type="checkbox" className="size-4 accent-primary" {...inputProps} />
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
    </div>
  );
}
