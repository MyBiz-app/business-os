"use client";

import { useEffect, useRef, useState } from "react";

export type HomePhoneLabels = {
  title: string;
  days: string[];
  classes: string[];
  friendsTitle: string;
  friends: string[];
  friendsNote: string;
  inviteTitle: string;
  inviteClass: string;
  inviteFriend: string;
  inviteCta: string;
  inviteSent: string;
};

const SCREENS = 3;
const SWAP_MS = 4200;
const BLOCKS = [
  { time: "07:00", top: 0, height: 52, color: "#ec4899" },
  { time: "09:30", top: 64, height: 76, color: "#10b981" },
  { time: "18:00", top: 152, height: 52, color: "#f59e0b" },
];
const AVATARS = ["from-pink-500 to-rose-400", "from-emerald-500 to-teal-400", "from-amber-500 to-orange-400", "from-sky-500 to-indigo-400"];

function calm() {
  return (
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    document.documentElement.dataset.motion === "reduce"
  );
}

/** Tilts toward the pointer (desktop) and with the page scroll, and swaps the screen on a timer.
 * Reduced motion keeps one still screen. The phone is decorative, so it is hidden from assistive tech. */
export function HomePhoneStage({ labels }: { labels: HomePhoneLabels }) {
  const ref = useRef<HTMLDivElement>(null);
  const [screen, setScreen] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element || calm()) return;
    let frame = 0;
    const set = (x: number, y: number) => {
      element.style.setProperty("--px", Math.max(-1, Math.min(1, x)).toFixed(3));
      element.style.setProperty("--py", Math.max(-1, Math.min(1, y)).toFixed(3));
    };
    const onMove = (event: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = element.getBoundingClientRect();
        if (box.bottom < 0 || box.top > window.innerHeight) return;
        set(((event.clientX - box.left) / box.width - 0.5) * 2, ((event.clientY - box.top) / box.height - 0.5) * 2);
      });
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = element.getBoundingClientRect();
        const progress = (box.top + box.height / 2) / window.innerHeight - 0.5;
        element.style.setProperty("--sy", Math.max(-1, Math.min(1, progress * 2)).toFixed(3));
      });
    };
    const hover = window.matchMedia("(hover: hover)").matches;
    if (hover) window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      const box = element.getBoundingClientRect();
      if (box.bottom < 0 || box.top > window.innerHeight) return;
      setScreen((current) => (current + 1) % SCREENS);
    }, SWAP_MS);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("scroll", onScroll);
      window.clearInterval(timer);
    };
  }, []);

  const pane = (index: number) =>
    `absolute inset-0 flex flex-col transition-all duration-700 ease-out motion-reduce:transition-none ${
      screen === index ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
    }`;

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="mx-auto w-64 [--px:0] [--py:0] [--sy:0] [perspective:1100px]"
    >
      <div
        className="relative [transform-style:preserve-3d] transition-transform duration-300 ease-out motion-reduce:transition-none"
        style={{
          transform:
            "rotateX(calc(6deg + var(--py) * -8deg + var(--sy) * 5deg)) rotateY(calc(-14deg + var(--px) * 12deg))",
        }}
      >
        {/* soft glow under the phone */}
        <div className="absolute inset-x-6 -bottom-6 h-10 rounded-full bg-primary/30 blur-2xl [transform:translateZ(-60px)]" />
        <div className="relative h-[27rem] rounded-[2.5rem] border-[10px] border-foreground/85 bg-background p-3 shadow-2xl">
          <div className="mx-auto mb-3 h-1.5 w-16 rounded-full bg-foreground/20" />
          <div className="relative h-[calc(100%-1.125rem)] overflow-hidden">
            {/* Screen 1: schedule */}
            <div className={pane(0)}>
              <p className="mb-2 text-base font-bold">{labels.title}</p>
              <div className="mb-3 flex gap-1.5" dir="ltr">
                {labels.days.slice(0, 4).map((day, index) => (
                  <span
                    key={day}
                    className={`flex h-12 flex-1 flex-col items-center justify-center rounded-xl text-[11px] font-bold ${
                      index === 1 ? "bg-primary text-on-primary" : "border border-border"
                    }`}
                  >
                    {day}
                    <span className="text-sm">{4 + index}</span>
                  </span>
                ))}
              </div>
              <div className="relative flex-1" dir="ltr">
                {BLOCKS.map((block, index) => (
                  <div
                    key={block.time}
                    className="absolute inset-x-0 rounded-xl px-2.5 py-1.5 text-white [transform:translateZ(18px)] shadow-lg"
                    style={{ top: block.top, height: block.height, backgroundColor: block.color }}
                  >
                    <p className="text-[10px] font-bold tabular-nums opacity-90">{block.time}</p>
                    <p className="truncate text-xs font-bold">{labels.classes[index]}</p>
                  </div>
                ))}
              </div>
            </div>
            {/* Screen 2: friends */}
            <div className={pane(1)}>
              <p className="mb-3 text-base font-bold">{labels.friendsTitle}</p>
              <div className="mb-4 flex -space-x-2 rtl:space-x-reverse" dir="ltr">
                {labels.friends.map((name, index) => (
                  <span
                    key={name}
                    className={`flex size-12 items-center justify-center rounded-full border-2 border-background bg-gradient-to-br text-sm font-bold text-white shadow-md [transform:translateZ(20px)] ${AVATARS[index]}`}
                  >
                    {name.slice(0, 1)}
                  </span>
                ))}
              </div>
              <ul className="flex flex-col gap-2">
                {labels.friends.slice(0, 3).map((name, index) => (
                  <li key={name} className="flex items-center gap-2 rounded-2xl border border-border p-2.5">
                    <span className={`size-8 rounded-full bg-gradient-to-br ${AVATARS[index]}`} />
                    <span className="flex-1 truncate text-xs font-semibold">{name}</span>
                    <span className="size-2 rounded-full bg-success" />
                  </li>
                ))}
              </ul>
              <p className="mt-3 rounded-xl bg-primary/10 px-3 py-2 text-[11px] font-semibold text-primary">{labels.friendsNote}</p>
            </div>
            {/* Screen 3: invite */}
            <div className={pane(2)}>
              <p className="mb-3 text-base font-bold">{labels.inviteTitle}</p>
              <div className="rounded-2xl border border-border p-3 shadow-lg [transform:translateZ(22px)]">
                <p className="text-[11px] font-bold tabular-nums text-muted" dir="ltr">{labels.inviteClass}</p>
                <div className="my-3 flex items-center gap-2">
                  <span className={`flex size-10 items-center justify-center rounded-full bg-gradient-to-br text-sm font-bold text-white ${AVATARS[0]}`}>
                    {labels.inviteFriend.slice(0, 1)}
                  </span>
                  <span className="text-sm font-semibold">{labels.inviteFriend}</span>
                </div>
                <span className="block rounded-xl bg-primary py-2 text-center text-xs font-bold text-on-primary">{labels.inviteCta}</span>
              </div>
              <p className="mt-3 rounded-xl bg-success/15 px-3 py-2 text-[11px] font-semibold">{labels.inviteSent}</p>
            </div>
          </div>
        </div>
      </div>
      {/* screen dots */}
      <div className="mt-6 flex justify-center gap-1.5">
        {Array.from({ length: SCREENS }, (_, index) => (
          <span
            key={index}
            className={`h-1.5 rounded-full transition-all duration-500 ${screen === index ? "w-5 bg-primary" : "w-1.5 bg-foreground/20"}`}
          />
        ))}
      </div>
    </div>
  );
}
