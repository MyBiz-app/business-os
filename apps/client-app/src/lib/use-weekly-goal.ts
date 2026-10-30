import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";

export const GOALS = [1, 2, 3, 4, 5] as const;
const DEFAULT_GOAL = 2;

/** The client's own "visits a week" goal in one business. It lives on this phone only: it is a personal
 * target, not something the business needs to know. */
export function useWeeklyGoal(businessId: string | undefined): [number, (goal: number) => void] {
  const key = `progress.goal.${businessId ?? "none"}`;
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  useEffect(() => {
    if (!businessId) return;
    void AsyncStorage.getItem(key)
      .then((stored) => {
        const value = Number(stored);
        if ((GOALS as readonly number[]).includes(value)) setGoal(value);
      })
      .catch(() => undefined);
  }, [key, businessId]);
  const change = useCallback(
    (next: number) => {
      setGoal(next);
      void AsyncStorage.setItem(key, String(next)).catch(() => undefined);
    },
    [key],
  );
  return [goal, change];
}
