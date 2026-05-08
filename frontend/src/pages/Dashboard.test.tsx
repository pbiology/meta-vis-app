import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import Dashboard from "./Dashboard";

const API = "*/api/v1";

describe("Dashboard", () => {
  it("renders an inline warning when any data source fails", async () => {
    server.use(http.get(`${API}/cases/stats`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<Dashboard />, { route: "/" });
    expect(await screen.findByText(/some dashboard data failed to load/i)).toBeInTheDocument();
  });
});
