"use client";

/** A row of buttons where one is active (text size, contrast, motion). The look matches the
 * linked `Segmented` used on the shift board; this one changes a setting in place. */
export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex rounded-xl bg-surface-2 p-0.5 ring-1 ring-border"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`btn-plain rounded-[0.6rem] px-3 py-1.5 text-sm transition-colors ${
            value === option.value
              ? "bg-surface font-semibold text-foreground shadow-sm"
              : "text-muted hover:text-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
