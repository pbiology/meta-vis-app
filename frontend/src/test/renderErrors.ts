/**
 * Render errors captured by the test error boundary in utils.tsx.
 *
 * React unmounts the whole tree when a component throws during render, so
 * without a boundary the failure reaches Vitest as an unhandled error
 * attributed to the *file* rather than to the test that caused it. That is how
 * a crashing CaseView once passed its own smoke test: the page threw, rendered
 * nothing, and the assertion (`document.body` is truthy) still held.
 *
 * The boundary records here and setup.ts fails the test in afterEach, which
 * turns those floating errors into ordinary named failures carrying the real
 * message.
 *
 * Lives in its own module because both setup.ts and utils.tsx need it, and
 * utils.tsx already imports from setup.ts.
 */

let captured: Error | null = null;

/** Record a render error. The first one wins — later ones are usually fallout. */
export function recordRenderError(error: Error): void {
  captured ??= error;
}

/** Return the captured error, if any, and clear it for the next test. */
export function takeRenderError(): Error | null {
  const error = captured;
  captured = null;
  return error;
}
