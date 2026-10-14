import { BrandMark } from "@/components/brand-mark";

/** Remembered for the browser session, so the launch screen plays on the first load only and
 * never on later page loads. Runs before the first paint; `data-splash="off"` hides it. */
const SKIP_CODE = `try{if(sessionStorage.getItem("splash"))document.documentElement.dataset.splash="off";else sessionStorage.setItem("splash","1")}catch(e){}`;

/**
 * The launch screen: the MyBiz mark draws itself in over the page, then fades away on its own
 * (pure CSS, see `.launch-splash` in globals.css), so it never waits for the page and cannot get
 * stuck. Light and dark follow the page tokens; reduced motion shows a short static fade.
 * Rendered once in the root layout.
 */
export function LaunchSplash({ nonce }: { nonce?: string }) {
  return (
    <>
      <script nonce={nonce} dangerouslySetInnerHTML={{ __html: SKIP_CODE }} />
      <div className="launch-splash" aria-hidden="true">
        <div className="launch-splash-mark">
          <BrandMark className="size-20" />
        </div>
      </div>
    </>
  );
}
