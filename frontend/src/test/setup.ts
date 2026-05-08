import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./server";

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
