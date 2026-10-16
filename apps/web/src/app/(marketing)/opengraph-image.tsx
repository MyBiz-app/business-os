import { markSvg } from "@business-os/brand";
import { messages as all } from "@business-os/i18n";
import { BRAND } from "@business-os/i18n/brand";
import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { visualRtl } from "@/lib/visual-rtl";

// Israel first: the shared picture speaks Hebrew, with the site's own font (Assistant, OFL, in
// ./fonts with its license) and the same words as the home page. The renderer draws left to
// right only, so each Hebrew line is passed in visual order.
const messages = all.he;
const hero = messages.marketing.hero;
const mark = `data:image/svg+xml;base64,${Buffer.from(markSvg()).toString("base64")}`;
const FONTS = join(process.cwd(), "src/app/(marketing)/fonts");
const [medium, extraBold] = await Promise.all([
  readFile(join(FONTS, "Assistant-Medium.ttf")),
  readFile(join(FONTS, "Assistant-ExtraBold.ttf")),
]);

export const alt = `${BRAND.name} - ${messages.app.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The picture shown when a marketing page is shared (WhatsApp, Facebook, LinkedIn). */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-end",
          padding: 80,
          background: "linear-gradient(135deg, #2563eb 0%, #7c3aed 55%, #06b6d4 100%)",
          color: "white",
          fontFamily: "Assistant",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 44, fontWeight: 800 }}>
          {BRAND.name}
          <img src={mark} width={72} height={72} alt="" />
        </div>
        <div style={{ marginTop: 48, fontSize: 80, fontWeight: 800, lineHeight: 1.1 }}>{visualRtl(hero.title)}</div>
        <div style={{ fontSize: 80, fontWeight: 800, lineHeight: 1.1, opacity: 0.85 }}>{visualRtl(hero.titleAccent)}</div>
        <div style={{ marginTop: 36, fontSize: 34, fontWeight: 500, opacity: 0.92 }}>{visualRtl(hero.eyebrow)}</div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Assistant", data: medium, weight: 500, style: "normal" },
        { name: "Assistant", data: extraBold, weight: 800, style: "normal" },
      ],
    },
  );
}
