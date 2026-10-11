import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";

/** The way back to the page above this one (the browser's Back button keeps working too).
 * The arrow points to the reading direction's start. */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="btn-ghost -ms-2 w-fit px-2 py-1 text-sm">
      <ArrowLeft aria-hidden="true" className="size-4 rtl:hidden" />
      <ArrowRight aria-hidden="true" className="hidden size-4 rtl:block" />
      {label}
    </Link>
  );
}
