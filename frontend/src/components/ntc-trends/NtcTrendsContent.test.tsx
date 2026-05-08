import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import NtcTrendsContent from "./NtcTrendsContent";

const API = "*/api/v1";

describe("NtcTrendsContent", () => {
  it("renders an error message when the trends endpoint 500s", async () => {
    server.use(http.get(`${API}/ntc/trends`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<NtcTrendsContent />, { route: "/ntc" });
    expect(await screen.findByText(/failed to load ntc trends/i)).toBeInTheDocument();
  });

  it("renders the summary line when trends data loads", async () => {
    server.use(
      http.get(`${API}/ntc/trends`, () =>
        HttpResponse.json({
          total_ntcs: 4,
          min_case_count: 2,
          read_counts: [],
          kingdom_breakdown: [],
          recurring_taxa: [],
        })
      )
    );
    renderWithProviders(<NtcTrendsContent />, { route: "/ntc" });
    expect(await screen.findByText(/4 DNA NTCs in the last 90 days/)).toBeInTheDocument();
    expect(screen.getByText(/no recurring taxa/i)).toBeInTheDocument();
  });
});
