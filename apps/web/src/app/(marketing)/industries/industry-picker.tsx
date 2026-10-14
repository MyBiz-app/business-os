"use client";

import type { Icon } from "@business-os/verticals";

import { VerticalIcon } from "@/components/vertical-icon";

export type PickerItem = { key: string; name: string; icon: Icon; color: string };

/** Scrolls to an industry's details, gently (instantly when the visitor prefers reduced motion). */
function scrollToIndustry(key: string) {
  const target = document.getElementById(`industry-${key}`);
  if (!target) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  target.focus({ preventScroll: true });
}

/** A grid of icon tiles, one per industry; each one jumps to that industry's details below. */
export function IndustryPicker({ items, label }: { items: PickerItem[]; label: string }) {
  return (
    <ul aria-label={label} className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {items.map(({ key, name, icon, color }) => (
        <li key={key}>
          <a
            href={`#industry-${key}`}
            onClick={(event) => {
              event.preventDefault();
              scrollToIndustry(key);
            }}
            className="card card-hover group flex h-full flex-col items-center gap-3 p-5 text-center transition-transform duration-300 hover:scale-[1.06] focus-visible:scale-[1.06] motion-reduce:transition-none motion-reduce:hover:scale-100 motion-reduce:focus-visible:scale-100"
          >
            <span aria-hidden="true" className={`flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br ${color} text-white shadow-lg transition-transform duration-300 group-hover:-rotate-3 group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:transform-none`}>
              <VerticalIcon icon={icon} className="size-7" />
            </span>
            <span className="font-semibold">{name}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
