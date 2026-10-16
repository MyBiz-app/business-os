"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { useToast } from "@/components/toast/toaster";

/** After signing out the landing page opens with `?signed_out=1`: show a short confirmation once
 * and drop the flag from the address so a reload or a shared link doesn't repeat it. */
export function SignedOutNotice() {
  const t = useTranslations("marketing");
  const toast = useToast();

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("signed_out") !== "1") return;
    url.searchParams.delete("signed_out");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    toast("success", t("signedOut"));
  }, [t, toast]);

  return null;
}
