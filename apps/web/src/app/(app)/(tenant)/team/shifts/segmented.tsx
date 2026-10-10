import Link from "next/link";

/** A small row of linked choices (one active), for switching the board's range or view. */
export function Segmented({ label, items }: { label: string; items: { key: string; label: string; href: string; active: boolean }[] }) {
  return (
    <nav aria-label={label} className="flex rounded-xl bg-surface-2 p-0.5 ring-1 ring-border">
      {items.map((item) => (
        <Link
          key={item.key}
          href={item.href}
          aria-current={item.active ? "true" : undefined}
          className={`rounded-[0.6rem] px-3 py-1.5 text-sm transition-colors ${item.active ? "bg-surface font-semibold text-foreground shadow-sm" : "text-muted hover:text-foreground"}`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
