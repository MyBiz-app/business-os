/** Which side-menu area and sub-item the open page belongs to (R12). Kept out of the component so
 * it can be tested without a browser. */
export type NavLeaf = { href: string };
export type NavNode = { href: string; children?: NavLeaf[] };

export const pathOf = (href: string) => href.split("#")[0];
export const anchorOf = (href: string) => (href.includes("#") ? href.split("#")[1] : null);

/** The area for `pathname`: the most specific address wins (`/clients/join` over `/clients`), and
 * a sub-page wins a tie with its own area. Section links (`/ai#ai-team`) never match a page. */
export function matchArea<T extends NavNode>(items: T[], pathname: string): { item: T; href: string; child: boolean } | undefined {
  const links = items.flatMap((item) => [
    { href: item.href, item, child: false },
    ...(item.children ?? []).filter((c) => !c.href.includes("#")).map((c) => ({ href: c.href, item, child: true })),
  ]);
  return links
    .filter((link) => pathname === link.href || pathname.startsWith(`${link.href}/`))
    .sort((a, b) => b.href.length - a.href.length || Number(b.child) - Number(a.child))[0];
}

/** Sub-items that differ by a query (`/catalog?tab=plans`): the one named in the address, else the first. */
export function matchQueryChild(children: NavLeaf[], pathname: string, tab: string | null): string | null {
  const kids = children.filter((c) => c.href.includes("?") && pathOf(c.href.split("?")[0]) === pathname);
  if (kids.length === 0) return null;
  return (kids.find((c) => new URLSearchParams(c.href.split("?")[1]).get("tab") === tab) ?? kids[0]).href;
}

/** The section ids of the open page that its area lists as sub-items, in order. */
export function sectionAnchors(children: NavLeaf[], pathname: string): string[] {
  return children.flatMap((c) => (c.href.includes("#") && pathOf(c.href) === pathname ? [anchorOf(c.href) as string] : []));
}
