/** The public status page (UptimeRobot / Better Stack), set once it exists. Until then the
 * "System status" links stay hidden. Only an https address is used. */
export function statusPageUrl(value: string | undefined = process.env.NEXT_PUBLIC_STATUS_URL): string | undefined {
  return value?.startsWith("https://") ? value : undefined;
}
