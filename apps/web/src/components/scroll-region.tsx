/** A wide table that scrolls sideways on narrow screens. Keyboard users can focus it and
 * scroll with the arrow keys (WCAG: scrollable regions must be focusable). */
export function ScrollRegion({
  labelledBy,
  label,
  className = "",
  children,
}: {
  labelledBy?: string;
  label?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="region" aria-labelledby={labelledBy} aria-label={label} tabIndex={0} className={`overflow-x-auto ${className}`}>
      {children}
    </div>
  );
}
