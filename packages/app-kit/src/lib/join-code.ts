/** The join code in what a QR code or a link carries: a bare code, `mybiz://join?code=ABC123`, or
 * a web link `https://…/join/ABC123`. Returns null when nothing looks like a code. */
export function joinCodeFromScan(value: string): string | null {
  const text = value.trim();
  const fromQuery = /[?&]code=([A-Za-z0-9]+)/.exec(text);
  const fromPath = /\/join\/([A-Za-z0-9]+)/.exec(text);
  const raw = fromQuery?.[1] ?? fromPath?.[1] ?? (/^[A-Za-z0-9]{4,16}$/.test(text) ? text : null);
  return raw ? raw.toUpperCase() : null;
}
