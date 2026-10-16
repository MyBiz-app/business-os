/* eslint-disable @next/next/no-img-element -- the faces are small fingerprinted files from our own package */
import { avatarFor } from "./avatars";
import type { Agent } from "./types";

type Face = Pick<Agent, "key" | "name" | "color" | "avatar_preset"> & { avatar_key?: string | null; avatar_url?: string | null };

/** The picture of an uploaded face, served through the web app so the browser sends the session. */
export function uploadedFace(agent: Pick<Face, "key" | "avatar_key" | "avatar_url">): string | null {
  return agent.avatar_url && agent.avatar_key ? `/ai-avatars/${encodeURIComponent(agent.key)}?v=${agent.avatar_key}` : null;
}

/** An agent's face, or its initial on its color when a custom agent has no picture yet. */
export function AgentAvatar({ agent, className = "" }: { agent: Face; className?: string }) {
  const src = uploadedFace(agent) ?? avatarFor(agent.avatar_preset, agent.key);
  if (src) return <img src={src} alt="" draggable={false} className={`rounded-full object-cover ${className}`} />;
  return (
    <span aria-hidden="true" className={`grid place-items-center rounded-full font-semibold text-white ${className}`} style={{ backgroundColor: agent.color }}>
      {Array.from(agent.name)[0] ?? "?"}
    </span>
  );
}
