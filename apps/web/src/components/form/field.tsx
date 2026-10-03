import { useId } from "react";

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
      <input
        id={id}
        aria-describedby={hintId}
        className="rounded-lg border border-border bg-background px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-primary"
        {...inputProps}
      />
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

type SelectFieldProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: { value: string; label: string }[];
};

export function SelectField({ label, options, ...selectProps }: SelectFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={id}
        className="rounded-lg border border-border bg-background px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-primary"
        {...selectProps}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
