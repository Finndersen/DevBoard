// This file runs before all other setup files so that globals like localStorage
// are in place before MSW (which accesses localStorage at module initialisation).

if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.getItem !== 'function') {
  const localStorageMock = (() => {
    let store: Record<string, string> = {}
    return {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = String(value) },
      removeItem: (key: string) => { delete store[key] },
      clear: () => { store = {} },
      key: (index: number) => Object.keys(store)[index] ?? null,
      get length() { return Object.keys(store).length },
    }
  })()

  Object.defineProperty(globalThis, 'localStorage', {
    writable: true,
    configurable: true,
    value: localStorageMock,
  })
}
