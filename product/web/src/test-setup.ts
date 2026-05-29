import "@testing-library/jest-dom/vitest";

// jsdom in this setup doesn't expose localStorage (opaque origin). The app persists
// the language choice there, so provide a minimal in-memory shim for tests.
if (typeof globalThis.localStorage === "undefined") {
  const store = new Map<string, string>();
  const mem = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => [...store.keys()][i] ?? null,
    removeItem: (k: string) => void store.delete(k),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
  };
  Object.defineProperty(globalThis, "localStorage", { value: mem, configurable: true });
}
