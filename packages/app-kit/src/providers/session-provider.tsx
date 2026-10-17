import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState } from "react";

import { registerDevice } from "../lib/device";
import { registerPushToken } from "../lib/push";
import { isSessionStale, needsCodeStep, shouldRefreshStamp } from "../lib/session-rules";
import { supabase } from "../lib/supabase";

/** `mfaPending`: the person has an authenticator but has not entered a code in this session. */
type SessionContextValue = { session: Session | null; loading: boolean; mfaPending: boolean };

const SessionContext = createContext<SessionContextValue | null>(null);
const ACTIVE_KEY = "security.lastActive";

async function readStamp(): Promise<number | null> {
  const value = Number(await AsyncStorage.getItem(ACTIVE_KEY));
  return Number.isFinite(value) && value > 0 ? value : null;
}

async function codeStepPending(session: Session | null): Promise<boolean> {
  if (!session) return false;
  const { data } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
  return needsCodeStep(data?.currentLevel, data?.nextLevel);
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionContextValue>({ session: null, loading: true, mfaPending: false });

  useEffect(() => {
    const apply = async (session: Session | null) => setState({ session, loading: false, mfaPending: await codeStepPending(session) });
    void (async () => {
      const { data } = await supabase.auth.getSession();
      // Not opened for thirty days: sign in again.
      const stamp = await readStamp();
      if (data.session && isSessionStale(stamp, Date.now())) {
        await AsyncStorage.removeItem(ACTIVE_KEY);
        await supabase.auth.signOut();
        return;
      }
      if (data.session && shouldRefreshStamp(stamp, Date.now())) await AsyncStorage.setItem(ACTIVE_KEY, String(Date.now()));
      await apply(data.session);
    })();
    // Not awaited here: calling Supabase from inside this callback would wait on its own lock.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setTimeout(() => void apply(session), 0);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = state.session?.user.id;
  const ready = Boolean(userId) && !state.mfaPending;
  useEffect(() => {
    if (!ready) return;
    void AsyncStorage.setItem(ACTIVE_KEY, String(Date.now()));
    void registerPushToken();
    void registerDevice();
  }, [ready, userId]);

  return <SessionContext.Provider value={state}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
