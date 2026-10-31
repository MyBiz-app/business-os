type Storage = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

/** Small things the app remembers on the phone (the business or area used last). The phone's
 * storage can fail (full, damaged, busy); that must never stop a person from signing in, so a read
 * that fails is "nothing remembered" and a write that fails is skipped. */
export function rememberedIn(storage: Storage) {
  return {
    read: (key: string): Promise<string | null> => storage.getItem(key).catch(() => null),
    write: (key: string, value: string): Promise<void> => storage.setItem(key, value).catch(() => undefined),
  };
}
