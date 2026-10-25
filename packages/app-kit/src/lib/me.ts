import { apiClient, unwrap } from "./api";
import { FRESH_MS, queryClient } from "./query-client";
import { supabase } from "./supabase";

/** The signed-in person's own record. Screens that open together share one request, and a copy
 * seen a moment ago is reused. */
export async function fetchMe() {
  const { data } = await supabase.auth.getSession();
  const userId = data.session?.user.id ?? "";
  return queryClient.fetchQuery({
    queryKey: [userId, "me"],
    queryFn: async () => unwrap(await apiClient().GET("/me")),
    staleTime: FRESH_MS,
  });
}
