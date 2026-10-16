"use server";

import { getApi } from "@/lib/api";

/** Records what the person did with a pop-up (the API checks it was meant for them). */
export async function markAnnouncement(id: string, event: "viewed" | "dismissed" | "clicked"): Promise<void> {
  const api = await getApi();
  await api.POST("/me/announcements/{announcement_id}/{event}", { params: { path: { announcement_id: id, event } } });
}
