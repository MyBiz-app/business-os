import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { SessionBody } from "./[id]/session-body";

/** A class or booking opened as a window over the schedule (`/schedule?open=<id>`). */
export async function SessionWindow({ id, closeHref }: { id: string; closeHref: string }) {
  const { api, scope } = await getTenantFor("schedule.read");
  const { data: session } = await api.GET("/sessions/{session_id}", { params: { ...scope, path: { session_id: id } } });
  if (!session) notFound();
  return (
    <RouteModal title={session.service.name} size="md" transitionName={`session-${id}`} closeHref={closeHref}>
      <SessionBody id={id} query={{}} inModal />
    </RouteModal>
  );
}
