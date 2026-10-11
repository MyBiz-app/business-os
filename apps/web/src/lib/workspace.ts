/** Where the web app serves the business's cover image (members only), from the API's
 * `cover_url` (its `?v=` version lets the browser keep it). */
export function coverSrc(apiPath: string): string {
  return `/workspace-cover?v=${apiPath.split("?v=")[1] ?? ""}`;
}
