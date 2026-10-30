import AsyncStorage from "@react-native-async-storage/async-storage";

import { pushAvailable, pushPermission } from "./push";
import { shouldOfferPush } from "./push-offer-rules";

const KEY = "push.offer.answeredAt";
const listeners = new Set<() => void>();

/** Called by a screen right after a booking went through; the offer sheet decides whether to show. */
export function offerPushAfterBooking(): void {
  if (!pushAvailable) return;
  listeners.forEach((listener) => listener());
}

/** The offer sheet listens here; returns the way to stop. */
export function onPushOffer(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function lastAnswer(): Promise<number | null> {
  try {
    const value = Number(await AsyncStorage.getItem(KEY));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

/** True when the sheet should open now. */
export async function pushOfferDue(): Promise<boolean> {
  return shouldOfferPush({ available: pushAvailable, permission: await pushPermission(), lastAnswerAt: await lastAnswer() });
}

/** The person said "Not now": do not offer again for a while. */
export async function snoozePushOffer(): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, String(Date.now()));
  } catch {
    // the offer may come back sooner; nothing is lost
  }
}
