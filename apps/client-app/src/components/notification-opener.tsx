import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { useEffect, useRef } from "react";

import { areaForNotification } from "@business-os/app-kit/lib/areas";
import { useAreas } from "@/providers/area-provider";

/** Tapping a push opens the business it came from (its brand, its data) and its updates, instead
 * of whatever was open. Works for a tap while the app runs and for the tap that started it. A push
 * from a business the person has no area in opens nothing. Native only: there are no pushes on
 * the web. */
export function NotificationOpener() {
  const { areas, switchTo } = useAreas();
  const response = Notifications.useLastNotificationResponse();
  const handled = useRef<string | null>(null);

  useEffect(() => {
    if (!response || !areas) return;
    const id = response.notification.request.identifier;
    if (handled.current === id) return;
    handled.current = id;
    const area = areaForNotification(areas, response.notification.request.content.data?.tenant_id);
    if (!area) return;
    void switchTo(area.key).then(() => {
      if (area.kind === "client") router.navigate("/updates");
    });
  }, [response, areas, switchTo]);

  return null;
}
