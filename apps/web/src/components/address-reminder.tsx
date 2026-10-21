import { MapPin } from "lucide-react";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

/** Reminds team members who have not filled in their home address (city, street, house number)
 * until they do. Existing people are not locked out: it is only a line at the top. */
export async function AddressReminder({ show }: { show: boolean }) {
  if (!show) return null;
  const t = await getTranslations("address.reminder");
  return (
    <div role="status" className="flex flex-wrap items-center justify-center gap-3 border-b border-border bg-primary/5 px-4 py-2 text-sm">
      <MapPin aria-hidden="true" className="size-4" />
      <span>{t("text")}</span>
      <Link href="/account#profile" className="inline-block py-2 font-medium underline underline-offset-4 md:py-0">
        {t("action")}
      </Link>
    </div>
  );
}
