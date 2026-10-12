export type SwapStatus = "pending_colleague" | "pending_manager" | "approved" | "declined" | "refused" | "cancelled";

const OPEN: readonly SwapStatus[] = ["pending_colleague", "pending_manager"];

export function isOpenSwap(status: SwapStatus): boolean {
  return OPEN.includes(status);
}

/** A shift can be offered when it is published, has not started and no swap for it is open;
 * the API repeats these rules. */
export function canOfferSwap(
  shift: { id: string; starts_at: string; published: boolean },
  swaps: { shift_id: string; status: SwapStatus }[],
  now: Date,
): boolean {
  if (!shift.published || Date.parse(shift.starts_at) <= now.getTime()) return false;
  return !swaps.some((swap) => swap.shift_id === shift.id && isOpenSwap(swap.status));
}
