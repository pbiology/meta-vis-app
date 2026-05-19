import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./server";

// Stub react-oidc-context so components that read auth state get a
// deterministic, authenticated user without spinning up a real OIDC provider.
// Tests that need an unauthenticated state set `__authState.isAuthenticated`
// to false before rendering (see test/utils.tsx).
export const __authState = {
  isAuthenticated: true,
  isLoading: false,
  preferredUsername: "tester",
  roles: ["admin"] as string[],
};
// Construct a JWT-shaped access token (unsigned). The frontend decodes the
// payload to read client roles; the signature is never checked here, so any
// value works in the `sig` slot.
function fakeAccessToken(): string {
  const roleClient = "meta-vis-frontend";
  const payload = {
    sub: `sub-${__authState.preferredUsername}`,
    preferred_username: __authState.preferredUsername,
    resource_access: { [roleClient]: { roles: __authState.roles } },
  };
  const b64 = (obj: object) => Buffer.from(JSON.stringify(obj)).toString("base64url");
  return `${b64({ alg: "none", typ: "JWT" })}.${b64(payload)}.sig`;
}
vi.mock("react-oidc-context", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => ({
    isAuthenticated: __authState.isAuthenticated,
    isLoading: __authState.isLoading,
    user: __authState.isAuthenticated
      ? {
          access_token: fakeAccessToken(),
          expired: false,
          profile: {
            sub: `sub-${__authState.preferredUsername}`,
            preferred_username: __authState.preferredUsername,
          },
        }
      : null,
    signinRedirect: vi.fn().mockResolvedValue(undefined),
    signoutRedirect: vi.fn().mockResolvedValue(undefined),
    signinSilent: vi.fn().mockResolvedValue(undefined),
    error: undefined,
  }),
}));

// The axios client imports the OIDC UserManager singleton from src/oidc.ts;
// in tests we don't need real token management, just a stub.
vi.mock("../oidc", () => ({
  userManager: {
    getUser: vi.fn().mockResolvedValue(null),
    signinRedirect: vi.fn().mockResolvedValue(undefined),
    signinSilent: vi.fn().mockResolvedValue(undefined),
    signoutRedirect: vi.fn().mockResolvedValue(undefined),
  },
  oidcConfig: {},
}));

// Node 22+ ships an experimental Storage that overrides jsdom's implementation
// when `--localstorage-file` is detected; it surfaces as `setItem is not a
// function`. Force a deterministic in-memory Storage on both globals.
class MemStorage implements Storage {
  private map = new Map<string, string>();
  get length() {
    return this.map.size;
  }
  clear() {
    this.map.clear();
  }
  getItem(k: string) {
    return this.map.has(k) ? (this.map.get(k) as string) : null;
  }
  key(i: number) {
    return Array.from(this.map.keys())[i] ?? null;
  }
  removeItem(k: string) {
    this.map.delete(k);
  }
  setItem(k: string, v: string) {
    this.map.set(k, String(v));
  }
}
Object.defineProperty(globalThis, "localStorage", {
  value: new MemStorage(),
  configurable: true,
});
Object.defineProperty(globalThis, "sessionStorage", {
  value: new MemStorage(),
  configurable: true,
});

// jsdom does not implement ResizeObserver, but charts in components/ntc-trends
// use it via useContainerWidth. Provide a no-op polyfill so component renders
// don't throw during tests.
class NoopResizeObserver implements ResizeObserver {
  observe() {
    /* no-op: tests don't react to size changes */
  }
  unobserve() {
    /* no-op */
  }
  disconnect() {
    /* no-op */
  }
}
if (globalThis.ResizeObserver === undefined) {
  Object.defineProperty(globalThis, "ResizeObserver", {
    value: NoopResizeObserver,
    configurable: true,
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  sessionStorage.clear();
  localStorage.clear();
});
afterAll(() => server.close());
