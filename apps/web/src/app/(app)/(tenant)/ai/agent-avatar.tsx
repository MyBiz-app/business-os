/* eslint-disable @next/next/no-img-element -- the faces are small fingerprinted files from our own package */
import { avatarFor } from "./avatars";
import type { Agent } from "./types";

/** An agent's face, or its initial on its color when a custom agent has no picture yet. */
export function AgentAvatar({ agent, className = "" }: { agent: Pick<Agent, "key" | "name" | "color" | "avatar_preset">; className?: string }) {
  const src = avatarFor(agent.avatar_preset, agent.key);
  if (src) return <img src={src} alt="" draggable={false} className={`rounded-full object-cover ${className}`} />;
  return (
    <span aria-hidden="true" className={`grid place-items-center rounded-full font-semibold text-white ${className}`} style={{ backgroundColor: agent.color }}>
      {Array.from(agent.name)[0] ?? "?"}
    </span>
  );
}
