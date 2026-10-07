import type { Tone } from "@/components/pill";

export const STATUS_TONE: Record<string, Tone> = {
  draft: "muted",
  sent: "primary",
  accepted: "success",
  declined: "danger",
  expired: "warning",
};
