import { Component, ReactElement, ReactNode } from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, RenderOptions } from "@testing-library/react";
import { AuthProvider } from "../context/AuthContext";
import { ReportBuilderProvider } from "../context/ReportBuilderContext";
import { __authState } from "./setup";
import { recordRenderError } from "./renderErrors";

interface RenderOpts extends Omit<RenderOptions, "wrapper"> {
  // Initial URL the MemoryRouter starts at.
  route?: string;
  // Optional <Route path> wrapper so that route params are populated.
  routePath?: string;
  // Pre-seed sessionStorage before the component mounts.
  sessionStorage?: Record<string, unknown>;
  // When true (default), the OIDC mock reports an authenticated user.
  authenticated?: boolean;
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

/**
 * Catches anything thrown while rendering so the failure can be attributed to
 * the test that caused it (see renderErrors.ts). Renders nothing on failure,
 * matching React's own behaviour of unmounting the tree — assertions that the
 * page rendered still fail, they just fail with a usable message.
 */
class RenderErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    recordRenderError(error);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

interface ProvidersProps {
  children: ReactNode;
  initialEntries: string[];
  routePath?: string;
}

function Providers({ children, initialEntries, routePath }: ProvidersProps) {
  const client = makeQueryClient();
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <ReportBuilderProvider>
          <MemoryRouter
            initialEntries={initialEntries}
            future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          >
            {routePath ? (
              <Routes>
                <Route path={routePath} element={children} />
                <Route path="*" element={children} />
              </Routes>
            ) : (
              children
            )}
          </MemoryRouter>
        </ReportBuilderProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(ui: ReactElement, opts: RenderOpts = {}) {
  const {
    route = "/",
    routePath,
    sessionStorage: sessionSeed,
    authenticated = true,
    ...rest
  } = opts;

  __authState.isAuthenticated = authenticated;
  __authState.isLoading = false;
  __authState.preferredUsername = "tester";
  __authState.roles = ["admin"];

  if (sessionSeed) {
    for (const [k, v] of Object.entries(sessionSeed)) {
      sessionStorage.setItem(k, JSON.stringify(v));
    }
  }

  return render(ui, {
    // The boundary sits outside the providers so a throw in any of them is
    // caught too, not just one in the component under test.
    wrapper: ({ children }) => (
      <RenderErrorBoundary>
        <Providers initialEntries={[route]} routePath={routePath}>
          {children}
        </Providers>
      </RenderErrorBoundary>
    ),
    ...rest,
  });
}
