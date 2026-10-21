import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cx } from "./cx";

/** primary: the one main action of a view. secondary: the default. quiet: cancel, back, toolbar
 * actions. danger: delete and remove. plain: the escape hatch for a button that is a whole card,
 * chip or row (it keeps the focus ring and touch behavior, and nothing else). */
export type ButtonVariant = "primary" | "secondary" | "quiet" | "danger" | "plain";
/** md is 36px tall on a desktop and 44px on a touch screen (the global rule in globals.css);
 * lg is the generous call to action. */
export type ButtonSize = "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  quiet: "btn-ghost",
  danger: "btn-danger",
  plain: "btn-plain",
};

/** The classes of a button, for the rare element that cannot be a `Button` (a form control that
 * renders its own element). Prefer `Button` and `ButtonLink`. */
export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", className?: string): string {
  if (variant === "plain") return cx(VARIANT.plain, className);
  return cx(VARIANT[variant], size === "lg" ? "min-h-11 px-5 text-base" : "min-h-9 px-3.5 text-sm", className);
}

type ButtonProps = Omit<ComponentProps<"button">, "type"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Waiting for a result: the button is disabled and announces that it is busy. */
  pending?: boolean;
  type?: "button" | "submit" | "reset";
};

/** The one button of the product. `type` defaults to "button", so a button inside a form never
 * submits by accident. */
export function Button({ variant = "secondary", size = "md", pending = false, type = "button", className, disabled, ...props }: ButtonProps) {
  return <button {...props} type={type} disabled={disabled || pending} aria-busy={pending || undefined} className={buttonClass(variant, size, className)} />;
}

type ButtonLinkProps = ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize };

/** A link that looks like a button (it goes somewhere; a `Button` does something). */
export function ButtonLink({ variant = "secondary", size = "md", className, ...props }: ButtonLinkProps) {
  return <Link {...props} className={buttonClass(variant, size, className)} />;
}

type IconButtonProps = Omit<ButtonProps, "children" | "size" | "aria-label"> & {
  /** What the button does, for screen readers and the tooltip. Required: an icon alone says nothing. */
  label: string;
  /** The icon (aria-hidden). */
  children: ReactNode;
};

/** An icon-only button: 36px square on a desktop, 44px on a touch screen. */
export function IconButton({ label, variant = "quiet", pending = false, type = "button", className, disabled, children, ...props }: IconButtonProps) {
  return (
    <button
      {...props}
      type={type}
      aria-label={label}
      title={props.title ?? label}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={cx(variant === "plain" ? "btn-plain" : `${VARIANT[variant]} btn-icon size-9 shrink-0 p-0`, className)}
    >
      {children}
    </button>
  );
}
