import { Check } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";

type ChoiceCardProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "title"
> & {
  type: "checkbox" | "radio";
  title: ReactNode;
  hint?: ReactNode;
};

/** A checkbox or radio as a whole-card target: a clear box or dot, the title, and a hint line.
 * The native input stays in the page (visually hidden) so keyboard and screen readers work. */
export function ChoiceCard({
  type,
  title,
  hint,
  className = "",
  ...input
}: ChoiceCardProps) {
  return (
    <label
      className={`group flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-surface p-3.5 text-sm transition-colors hover:border-primary/40 has-[:checked]:border-primary has-[:checked]:bg-primary/10 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary/40 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60 ${className}`.trim()}
    >
      <input type={type} className="sr-only" {...input} />
      <span
        aria-hidden="true"
        className={`mt-0.5 grid size-5 shrink-0 place-items-center border-2 border-border bg-surface text-on-primary transition-colors group-has-[:checked]:border-primary group-has-[:checked]:bg-primary ${type === "radio" ? "rounded-full" : "rounded-md"}`}
      >
        {type === "radio" ? (
          <span className="size-2 rounded-full bg-transparent group-has-[:checked]:bg-on-primary" />
        ) : (
          <Check
            className="size-3.5 opacity-0 group-has-[:checked]:opacity-100"
            strokeWidth={3}
          />
        )}
      </span>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium">{title}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </span>
    </label>
  );
}
