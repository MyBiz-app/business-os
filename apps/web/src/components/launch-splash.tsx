import { BrandMark } from "@/components/brand-mark";

/** Remembered for the browser session, so the launch screen plays on the first load only and
 * never on later page loads. Runs before the first paint; `data-splash="off"` hides it. */
const SKIP_CODE = `try{if(sessionStorage.getItem("splash"))document.documentElement.dataset.splash="off";else sessionStorage.setItem("splash","1")}catch(e){}`;

/**
 * The launch screen: the MyBiz mark flips in as a thick 3D tile (stacked layers) inside two
 * orbiting rings with a glow behind it, then the whole layer fades away on its own
 * (pure CSS, see `.launch-splash` in globals.css), so it never waits for the page and cannot get
 * stuck. Light and dark follow the page tokens; reduced motion shows a short static fade.
 * Rendered once in the root layout.
 */
export function LaunchSplash({ nonce }: { nonce?: string }) {
  return (
    <>
      <script nonce={nonce} dangerouslySetInnerHTML={{ __html: SKIP_CODE }} />
      <div className="launch-splash" aria-hidden="true">
        <div className="launch-stage">
          <span className="launch-glow" />
          <span className="launch-ring" />
          <span className="launch-ring launch-ring-2" />
          <div className="launch-splash-mark">
            <BrandMark className="launch-layer launch-layer-3" />
            <BrandMark className="launch-layer launch-layer-2" />
            <BrandMark className="launch-layer launch-layer-1" />
            <BrandMark className="launch-layer launch-layer-front" />
          </div>
        </div>
      </div>
    </>
  );
}
