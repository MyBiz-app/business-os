const SYMBOLS: Record<string, string> = { ILS: "₪", USD: "$", EUR: "€" };

/** A small round badge with the currency symbol, shown next to prices. Decorative: the amount carries the meaning. */
export function CurrencyBadge({ currency, className = "" }: { currency: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex size-[1.4em] shrink-0 items-center justify-center rounded-full bg-primary/10 text-[0.7em] font-bold text-primary motion-safe:transition-transform motion-safe:duration-300 group-hover:motion-safe:scale-110 ${className}`}
    >
      {SYMBOLS[currency] ?? currency}
    </span>
  );
}
