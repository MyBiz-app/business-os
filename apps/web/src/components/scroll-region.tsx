/** A wide table that scrolls sideways on narrow screens (a named group, not a landmark, so it
 * never duplicates the section around it). Keyboard users can focus it and
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
    <div role="group" aria-labelledby={labelledBy} aria-label={label} tabIndex={0} className={`relative overflow-x-auto ${className}`}>
      {children}
    </div>
  );
}
