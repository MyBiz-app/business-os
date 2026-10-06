/** Weekly hours, as the hours editor and its server actions exchange them (0 = Monday). */
export type Block = { weekday: number; starts: string; ends: string };
export type HoursState = { saved?: boolean; error?: "overlapping_hours" | "invalid" | "generic" };

/** The API's hour blocks ("09:00:00") as the editor shows them ("09:00"). */
export function toBlocks(blocks: { weekday: number; starts: string; ends: string }[]): Block[] {
  return blocks.map((block) => ({ weekday: block.weekday, starts: block.starts.slice(0, 5), ends: block.ends.slice(0, 5) }));
}

/** The week starts on Sunday in Israel and on Monday elsewhere (0 = Monday). */
export function weekStartFor(locale: string): number {
  return locale === "he" ? 6 : 0;
}
