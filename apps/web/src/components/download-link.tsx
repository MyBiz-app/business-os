import { Download } from "lucide-react";

/** A secondary button that downloads a file (the PDF of a document), hidden when printing. */
export function DownloadLink({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} download className="btn-secondary px-4 py-2 print:hidden">
      <Download aria-hidden="true" className="size-4" />
      {label}
    </a>
  );
}
