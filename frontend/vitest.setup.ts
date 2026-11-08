import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Auto-cleanup the DOM between tests so component state doesn't leak.
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Next.js navigation is normally provided by the App Router context.
// Component tests don't mount the App tree, so any `useRouter()` /
// `useSearchParams()` call would throw. Stub a sane default the
// individual tests can override with vi.mocked(...).
vi.mock("next/navigation", () => {
  const fns = {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  };
  const url = new URLSearchParams("");
  return {
    useRouter: () => fns,
    useSearchParams: () => url,
    usePathname: () => "/",
    redirect: vi.fn(),
    notFound: vi.fn(),
  };
});

// NextAuth's React hooks call into networking under the hood. The
// individual tests mock getSession() / signIn() with whatever payload
// they need; this base stub keeps imports resolvable.
vi.mock("next-auth/react", () => ({
  getSession: vi.fn(async () => null),
  useSession: () => ({ data: null, status: "unauthenticated" }),
  signIn: vi.fn(),
  signOut: vi.fn(),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// jsdom's window.matchMedia is missing — some Tailwind utility code uses it.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// jsdom in certain Vitest versions ships without localStorage attached to
// `window`. Polyfill a minimal Storage so components that touch
// localStorage during render don't crash.
if (typeof window !== "undefined" && !window.localStorage) {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k, v) => {
      store.set(k, String(v));
    },
    removeItem: (k) => {
      store.delete(k);
    },
    key: (i) => Array.from(store.keys())[i] ?? null,
  };
  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true,
  });
}
