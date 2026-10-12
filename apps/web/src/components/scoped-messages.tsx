import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import type { ReactNode } from "react";

import { CLIENT_NAMESPACES } from "@/i18n/client-namespaces";

type Scope = keyof typeof CLIENT_NAMESPACES;

/** The messages for one language, cut down to the namespaces the browser reads in these scopes
 * (the shared "root" ones are always included). */
export async function clientMessages(scopes: readonly Scope[]) {
  const wanted = new Set([...CLIENT_NAMESPACES.root, ...scopes.flatMap((scope) => CLIENT_NAMESPACES[scope])]);
  const all = await getMessages();
  return Object.fromEntries(Object.entries(all).filter(([namespace]) => wanted.has(namespace)));
}

/** Sends the browser only the words its part of the site uses (see scripts/client-namespaces.mjs).
 * A nested provider replaces its parent's messages, so list every scope the subtree needs. */
export async function ScopedMessages({ scopes, children }: { scopes: readonly Scope[]; children: ReactNode }) {
  return <NextIntlClientProvider messages={await clientMessages(scopes)}>{children}</NextIntlClientProvider>;
}
