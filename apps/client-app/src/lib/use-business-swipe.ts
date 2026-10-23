import { useMemo } from "react";
import { I18nManager, PanResponder } from "react-native";

import { neighbour, swipeStep } from "@business-os/app-kit/lib/all-mine";

/** A sideways swipe over the home screen moves to the next or previous business, for people who
 * prefer it to tapping the strip. Vertical scrolling is left alone. */
export function useBusinessSwipe(ids: string[], currentId: string | null, open: (tenantId: string) => void) {
  return useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, g) => Math.abs(g.dx) > 24 && Math.abs(g.dx) > Math.abs(g.dy) * 2,
        onPanResponderRelease: (_event, g) => {
          const step = swipeStep(g.dx, g.dy, I18nManager.isRTL);
          const target = step ? neighbour(ids, currentId, step) : null;
          if (target) open(target);
        },
      }).panHandlers,
    [ids, currentId, open],
  );
}
