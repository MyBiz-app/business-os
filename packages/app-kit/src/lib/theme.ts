// Same palette as the web app's marketing site; the values live in @business-os/design-tokens.
import { palette } from "@business-os/design-tokens";

export const colors = palette;

export type Palette = Record<keyof (typeof palette)["light"], string>;
