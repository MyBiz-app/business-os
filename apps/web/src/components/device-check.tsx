"use client";

import { BRAND } from "@business-os/i18n/brand";
import { useLocale } from "next-intl";
import { useEffect } from "react";

import { registerDevice } from "@/app/(app)/account/security-actions";

const FLAG = `${BRAND.app.storagePrefix}-device-checked`;

/** Once per browser session: lets the API know which browser this is (see registerDevice). */
export function DeviceCheck() {
  const locale = useLocale();
  useEffect(() => {
    try {
      if (window.sessionStorage.getItem(FLAG)) return;
      window.sessionStorage.setItem(FLAG, "1");
    } catch {
      return; // storage blocked: skip rather than check on every page
    }
    void registerDevice(locale);
  }, [locale]);
  return null;
}
