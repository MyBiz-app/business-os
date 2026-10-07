import "server-only";

import { safeNext } from "@/lib/navigation";
import { createClient } from "@/lib/supabase/server";

/** Where a new account was heading when it signed up (the sign-up journey's payment step or an
 * invitation), kept on the account itself. The cookie set at sign-up only lives in that browser,
 * and the confirmation email is often opened in another one (a mail app's own browser), so the
 * plan would otherwise be lost and the owner asked to set up the business again. */
const RESUME_KEY = "resume_path";

export function resumeMetadata(next: string | null): Record<string, string> | undefined {
  return next ? { [RESUME_KEY]: next } : undefined;
}

export async function resumePath(): Promise<string | null> {
  const { data } = await (await createClient()).auth.getUser();
  return safeNext(data.user?.user_metadata?.[RESUME_KEY]);
}

/** Once the business exists (or the invitation is accepted) there is nothing to resume. */
export async function clearResumePath(): Promise<void> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getUser();
  if (data.user?.user_metadata?.[RESUME_KEY]) await supabase.auth.updateUser({ data: { [RESUME_KEY]: null } });
}
