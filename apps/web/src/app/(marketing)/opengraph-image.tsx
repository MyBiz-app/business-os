import { ImageResponse } from "next/og";

export const alt = "MyBiz — business management and an AI workforce for small businesses";
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
          padding: 80,
          background: "linear-gradient(135deg, #4f46e5 0%, #c026d3 100%)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 44, fontWeight: 800 }}>
          <div style={{ width: 72, height: 72, borderRadius: 20, background: "rgba(255,255,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            M
          </div>
          MyBiz
        </div>
        <div style={{ marginTop: 48, fontSize: 76, fontWeight: 800, lineHeight: 1.05 }}>Run your business.</div>
        <div style={{ fontSize: 76, fontWeight: 800, lineHeight: 1.05, opacity: 0.85 }}>Grow it with AI.</div>
        <div style={{ marginTop: 36, fontSize: 30, opacity: 0.9 }}>Schedule · Clients · Payments · Client app · AI assistant — 14 days free</div>
      </div>
    ),
    size,
  );
}
