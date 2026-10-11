// Supabase sessions are bigger than the ~2 KB value limit of the phone's secure store (Keychain /
// Keystore), so a value is split into chunks: `key` holds the chunk count, `key.0`, `key.1`, ...
// hold the pieces. Pure logic on top of any async key-value backend, so it is unit-tested.

export interface KeyValueBackend {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export const CHUNK_SIZE = 1800;

export function createChunkedStorage(
  backend: KeyValueBackend,
  legacy?: KeyValueBackend,
  chunkSize = CHUNK_SIZE,
): KeyValueBackend {
  const chunkKey = (key: string, index: number) => `${key}.${index}`;

  async function removeItem(key: string): Promise<void> {
    const count = Number(await backend.getItem(key));
    if (Number.isInteger(count)) {
      for (let index = 0; index < count; index += 1) await backend.removeItem(chunkKey(key, index));
    }
    await backend.removeItem(key);
  }

  async function setItem(key: string, value: string): Promise<void> {
    await removeItem(key);
    const pieces: string[] = [];
    for (let at = 0; at < value.length; at += chunkSize) pieces.push(value.slice(at, at + chunkSize));
    for (const [index, piece] of pieces.entries()) await backend.setItem(chunkKey(key, index), piece);
    await backend.setItem(key, String(pieces.length));
  }

  async function getItem(key: string): Promise<string | null> {
    const header = await backend.getItem(key);
    if (header === null) {
      // A session saved before tokens moved to the secure store: move it over once.
      const old = legacy ? await legacy.getItem(key) : null;
      if (old === null || !legacy) return null;
      await setItem(key, old);
      await legacy.removeItem(key);
      return old;
    }
    const count = Number(header);
    if (!Number.isInteger(count) || count < 0) return null;
    let value = "";
    for (let index = 0; index < count; index += 1) {
      const piece = await backend.getItem(chunkKey(key, index));
      if (piece === null) return null; // a half-written value is treated as signed out
      value += piece;
    }
    return value;
  }

  return { getItem, setItem, removeItem };
}
