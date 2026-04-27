import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { taxprofilerProfile, tranaProfile } from "../test/fixtures/samples";
import { AuthProvider } from "../context/AuthContext";
import SampleDetail from "./SampleDetail";

const API = "*/api/v1";

function seedAuth() {
  localStorage.setItem("username", "tester");
  localStorage.setItem("role", "admin");
}

function renderTwoSamples(initial: string) {
  seedAuth();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter
          initialEntries={[initial]}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <nav>
            <Link to="/samples/A">go-A</Link>
            <Link to="/samples/B">go-B</Link>
          </nav>
          <Routes>
            <Route path="/samples/:sampleId" element={<SampleDetail />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("SampleDetail — cross-sample navigation", () => {
  it("resets activeTab when navigating from a kraken2-only sample to an emu-only sample", async () => {
    server.use(
      http.get(`${API}/samples/A`, () =>
        HttpResponse.json({ sample_id: "A", sample_type: "sample", taxprofiler: {} })
      ),
      http.get(`${API}/samples/A/profile`, () =>
        HttpResponse.json({ profiles: [taxprofilerProfile("kraken2")] })
      ),
      http.get(`${API}/samples/B`, () =>
        HttpResponse.json({ sample_id: "B", sample_type: "sample", trana: {} })
      ),
      http.get(`${API}/samples/B/profile`, () => HttpResponse.json({ profiles: [tranaProfile()] }))
    );

    // Neutralise the auth-context "Viruses" default so Bacteria rows aren't filtered.
    sessionStorage.setItem("taxonomy-filters", JSON.stringify({ kingdoms: [] }));
    renderTwoSamples("/samples/A");

    // Sample A: kraken2 tab should render with E. coli row.
    await waitFor(() => {
      expect(screen.getByText("Escherichia coli")).toBeInTheDocument();
    });

    // Navigate to sample B (trana / emu only).
    await userEvent.click(screen.getByRole("link", { name: "go-B" }));

    // Bug would leave activeTab="kraken2", causing TaxonomyTable to never render.
    // Assert a row from the trana fixture is visible — proves activeTab reset to "emu".
    await waitFor(() => {
      expect(screen.getByText("Influenza A virus")).toBeInTheDocument();
    });
  });

  it("renders full taxonomy when sessionStorage has stale metavalOnly:true and sample has no metaval", async () => {
    sessionStorage.setItem("taxonomy-filters", JSON.stringify({ metavalOnly: true }));
    server.use(
      http.get(`${API}/samples/A`, () =>
        HttpResponse.json({ sample_id: "A", sample_type: "sample", trana: {} })
      ),
      http.get(`${API}/samples/A/profile`, () => HttpResponse.json({ profiles: [tranaProfile()] })),
      http.get(`${API}/metaval/sample/A`, () => HttpResponse.json([]))
    );

    renderTwoSamples("/samples/A");

    // The trana sample's non-host rows should still appear despite the stale flag.
    await waitFor(() => {
      expect(screen.getByText("HIV-1")).toBeInTheDocument();
      expect(screen.getByText("Influenza A virus")).toBeInTheDocument();
    });
  });
});
