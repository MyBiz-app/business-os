"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Props = { clientsLabel: string };

export function SideNav({ clientsLabel }: Props) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const items = [
    { href: "/dashboard", label: t("dashboard") },
    { href: "/clients", label: clientsLabel },
  ];

  return (
    <nav aria-label={t("label")} className="border-b border-border md:border-b-0 md:border-e">
      <ul className="flex gap-1 overflow-x-auto p-3 md:w-56 md:flex-col">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`block whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
                  active ? "bg-primary/10 text-primary" : "text-muted hover:bg-surface hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
