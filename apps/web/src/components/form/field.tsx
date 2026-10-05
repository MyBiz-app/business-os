import { useId } from "react";

const CONTROL =
  "control w-full min-w-0 px-3 py-2";

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

export function Field({ label, hint, ...inputProps }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input id={id} aria-describedby={hintId} className={CONTROL} {...inputProps} />
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

type TextAreaFieldProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string };

export function TextAreaField({ label, ...textAreaProps }: TextAreaFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <textarea id={id} rows={4} className={CONTROL} {...textAreaProps} />
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
      <select id={id} className={CONTROL} {...selectProps}>
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
