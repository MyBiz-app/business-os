import { notFound } from "next/navigation";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { SessionBody } from "../../../schedule/[id]/session-body";

export default async function SessionModal({ params, searchParams }: PageProps<"/schedule/[id]">) {
  const { id } = await params;
  const { api, scope } = await getTenantFor("schedule.read");
  const { data: session } = await api.GET("/sessions/{session_id}", { params: { ...scope, path: { session_id: id } } });
  if (!session) notFound();
  return (
    <RouteModal title={session.service.name} size="md" transitionName={`session-${id}`}>
      <SessionBody id={id} query={await searchParams} inModal />
    </RouteModal>
  );
}
