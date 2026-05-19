import { ReactElement, ReactNode } from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, RenderOptions } from "@testing-library/react";
import { AuthProvider } from "../context/AuthContext";
import { ReportBuilderProvider } from "../context/ReportBuilderContext";
import { __authState } from "./setup";

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
    wrapper: ({ children }) => (
      <Providers initialEntries={[route]} routePath={routePath}>
        {children}
      </Providers>
    ),
    ...rest,
  });
}
