import type { ReactNode } from "react";

/** The catalog. A plan, service or discount code opened from the list shows in `modal` over the
 * list (an intercepting route); the same address opened directly is a normal page. */
export default function CatalogLayout({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
