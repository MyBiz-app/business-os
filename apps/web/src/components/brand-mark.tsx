import { LOGO_GRADIENT, MARK } from "@business-os/brand";

/** The MyBiz mark (gradient tile with the networked M), drawn from the shared brand package. */
export function BrandMark({ className }: { className?: string }) {
  // Every copy on a page defines the same gradient, so a shared id is harmless.
  const fill = "url(#mybiz-mark)";
  return (
    <svg viewBox={`0 0 ${MARK.size} ${MARK.size}`} fill="none" aria-hidden="true" focusable="false" className={className}>
      <defs>
        <linearGradient id="mybiz-mark" x1="0" y1="0" x2="1" y2="1">
          {LOGO_GRADIENT.map((color, i) => (
            <stop key={color} offset={i / (LOGO_GRADIENT.length - 1)} stopColor={color} />
          ))}
        </linearGradient>
      </defs>
      <rect width={MARK.size} height={MARK.size} rx={MARK.tileRadius} fill={fill} />
      <path d={MARK.path} stroke="white" strokeWidth={MARK.strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      {MARK.nodes.map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <circle cx={x} cy={y} r={MARK.nodeRadius} fill="white" />
          <circle cx={x} cy={y} r={MARK.nodeCoreRadius} fill={fill} />
        </g>
      ))}
    </svg>
  );
}
