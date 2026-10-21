"use client";

import { ChevronDown, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Menu, type MenuItem } from "@/components/ui/menu";

/** The "+ New" button of the home page: a short menu of the things people create most. */
export function NewMenu({ label, items }: { label: string; items: { key: string; label: string; href: string }[] }) {
  const menuItems: MenuItem[] = items.map((item) => ({ key: item.key, label: item.label, href: item.href }));
  return (
    <Menu
      label={label}
      items={menuItems}
      trigger={(props) => (
        <Button {...props} variant="primary">
          <Plus aria-hidden="true" className="size-4" />
          {label}
          <ChevronDown aria-hidden="true" className="size-4 opacity-70" />
        </Button>
      )}
    />
  );
}
