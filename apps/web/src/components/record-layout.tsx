"use client";

import { type ReactNode, useEffect, useState } from "react";

import { Tabs } from "./ui/tabs";

/** One tab of a record card: its content is rendered on the server and handed in as it is. */
export type RecordTab = {
  id: string;
  label: ReactNode;
  /** A count or short status after the label. */
  badge?: ReactNode;
  content: ReactNode;
};

/**
 * The Record page template (client, lead): a header above (the page brings it), underline tabs
 * under it, and the open tab's content in one column. Wide screens can add `aside`, a small column
 * of fixed details beside the content. Every tab stays mounted (hidden when not open), so a form
 * half filled in one tab is still there when the person comes back. An address `#tab` opens that
 * tab, so a link to a part of the card still lands on it.
 */
export function RecordLayout({ tabs, label, aside }: { tabs: RecordTab[]; label: string; aside?: ReactNode }) {
  const [active, setActive] = useState(tabs[0]?.id ?? "");

  useEffect(() => {
    const fromAddress = () => {
      const id = window.location.hash.slice(1);
      if (id && tabs.some((tab) => tab.id === id)) setActive(id);
    };
    // A link to `#tab` inside the page (the "Sell a plan" button) goes through Next's router, which
    // changes the address with pushState and fires no hashchange, so the click itself opens the tab.
    const fromLink = (event: MouseEvent) => {
      const href = (event.target as Element | null)?.closest?.("a[href^='#']")?.getAttribute("href");
      const id = href?.slice(1);
      if (id && tabs.some((tab) => tab.id === id)) setActive(id);
    };
    fromAddress();
    window.addEventListener("hashchange", fromAddress);
    document.addEventListener("click", fromLink);
    return () => {
      window.removeEventListener("hashchange", fromAddress);
      document.removeEventListener("click", fromLink);
    };
  }, [tabs]);

  function open(id: string) {
    setActive(id);
    try {
      window.history.replaceState(null, "", `#${id}`);
    } catch {
      // Not critical: the tab still opens.
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Tabs
        label={label}
        idPrefix="record"
        value={active}
        onChange={open}
        items={tabs.map((tab) => ({ value: tab.id, label: tab.label, badge: tab.badge }))}
      />
      <div className={aside ? "flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start xl:gap-8" : "flex flex-col gap-6"}>
        <div className="min-w-0">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              role="tabpanel"
              id={`record-panel-${tab.id}`}
              aria-labelledby={`record-tab-${tab.id}`}
              hidden={tab.id !== active}
              className="flex min-w-0 flex-col gap-6"
            >
              {tab.content}
            </div>
          ))}
        </div>
        {aside && <aside className="flex flex-col gap-4 lg:sticky lg:top-[calc(var(--sticky-top)+1rem)]">{aside}</aside>}
      </div>
    </div>
  );
}
