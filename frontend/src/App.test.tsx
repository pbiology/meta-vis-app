/**
 * Routing tests for the app's <Routes> composition.
 *
 * Every other test in the suite mounts a single page inside its own
 * MemoryRouter (see test/utils.tsx), which means the route table in App.tsx —
 * the redirects, the ProtectedRoute gating, and the Layout/Outlet nesting —
 * was never exercised. That is precisely the surface a react-router upgrade
 * changes, so these tests pin the behaviour that a version bump could
 * silently alter.
 *
 * Assertions read the resolved location rather than page content wherever the
 * behaviour under test is a redirect: asserting on a heading would also pass
 * if the target page happened to render for some other reason, whereas the
 * pathname is the thing the route table is actually responsible for.
 */
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import App from "./App";
import { renderWithProviders } from "./test/utils";

/** Renders the live location so redirect targets can be asserted directly. */
function LocationProbe() {
  const { pathname, search, hash } = useLocation();
  return <output data-testid="location">{pathname + search + hash}</output>;
}

function renderApp(route: string, opts: { authenticated?: boolean } = {}) {
  renderWithProviders(
    <>
      <App />
      <LocationProbe />
    </>,
    { route, ...opts }
  );
}

async function expectLocation(expected: string) {
  // Exact comparison, not toHaveTextContent: that matches substrings, so "/"
  // would be satisfied by every path in the app.
  await waitFor(() => expect(screen.getByTestId("location").textContent).toBe(expected));
}

describe("App routing", () => {
  // Bookmarks and external links to the pre-refactor /cases/:caseId page must
  // keep working; LegacyCaseRedirect in App.tsx is what preserves them.
  it("redirects the legacy case route to the case view", async () => {
    renderApp("/cases/abc123");
    await expectLocation("/case/abc123");
  });

  it("preserves the analysis version when redirecting the legacy case route", async () => {
    renderApp("/cases/abc123/analyses/2");
    await expectLocation("/case/abc123/analyses/2");
  });

  it("sends an unauthenticated user from a protected route to the landing page", async () => {
    renderApp("/cases", { authenticated: false });
    await expectLocation("/");
  });

  // Guards the nested <Route element={<Layout />}> + <Outlet /> arrangement:
  // if the nesting breaks, the child page never mounts.
  it("renders a protected page inside the app layout when authenticated", async () => {
    renderApp("/cases");
    await expectLocation("/cases");
    expect(await screen.findByRole("heading", { name: "Cases" })).toBeInTheDocument();
  });
});
