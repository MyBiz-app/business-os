/** Calls the app makes by itself, which change nothing a screen shows. */
const BACKGROUND_PATHS = /^\/me\/(devices|push-tokens)/;

/** Watches every API answer: any answer proves the network is up, and a change the person made
 * means their saved copies of other screens are old.
 *
 * It returns nothing on purpose. openapi-fetch treats a returned value as a replacement response and
 * throws unless it is `instanceof Response`; the phone's fetch can hand back a response of another
 * class, which made every call fail after the server had answered 200. */
export function responseObserver(deps: { markOnline: () => void; invalidateAll: () => void }) {
  return {
    onResponse({ request, response }: { request: Request; response: Response }): void {
      deps.markOnline();
      if (response.ok && request.method !== "GET" && !BACKGROUND_PATHS.test(new URL(request.url).pathname)) {
        deps.invalidateAll();
      }
    },
  };
}
