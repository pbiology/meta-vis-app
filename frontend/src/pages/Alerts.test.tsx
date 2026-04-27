import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import Alerts from "./Alerts";

const API = "*/api/v1";

function outbreak(id: number, name: string, caseIds: string[] = ["C-1"]) {
  return {
    taxon_id: id,
    taxon_name: name,
    config_name: "default",
    superkingdoms: ["Viruses"],
    case_ids: caseIds,
    cases: caseIds.map((c) => ({ case_id: c, order_date: "2026-04-20" })),
  };
}

describe("Alerts", () => {
  it("renders outbreak sections returned by the API", async () => {
    server.use(
      http.get(`${API}/alerts/outbreaks`, () =>
        HttpResponse.json({ window_days: 14, outbreaks: [outbreak(11676, "HIV-1")] })
      )
    );

    renderWithProviders(<Alerts />, { route: "/alerts" });
    expect(await screen.findByText("HIV 1")).toBeInTheDocument();
  });

  it("clicking the 30d window button refetches with window_days=30", async () => {
    let lastWindow = 0;
    server.use(
      http.get(`${API}/alerts/outbreaks`, ({ request }) => {
        lastWindow = Number(new URL(request.url).searchParams.get("window_days") ?? 0);
        return HttpResponse.json({ window_days: lastWindow, outbreaks: [] });
      })
    );

    renderWithProviders(<Alerts />, { route: "/alerts" });
    await waitFor(() => expect(lastWindow).toBe(14));

    await userEvent.click(screen.getByRole("button", { name: "30d" }));
    await waitFor(() => expect(lastWindow).toBe(30));
  });

  it("Ignore button posts to ignorelist and disables the button", async () => {
    let posted = false;
    server.use(
      http.get(`${API}/alerts/outbreaks`, () =>
        HttpResponse.json({ window_days: 14, outbreaks: [outbreak(99, "TestVirus")] })
      ),
      http.post(`${API}/alerts/ignorelist`, () => {
        posted = true;
        return HttpResponse.json({
          taxon_id: 99,
          taxon_name: "TestVirus",
          superkingdom: "Viruses",
          added_by: "tester",
          added_at: "2026-04-27",
          reason: null,
        });
      })
    );

    renderWithProviders(<Alerts />, { route: "/alerts" });
    const ignore = await screen.findByRole("button", { name: "Ignore" });
    await userEvent.click(ignore);
    await waitFor(() => expect(posted).toBe(true));
  });

  it("renders the all-clear empty state when no outbreaks", async () => {
    renderWithProviders(<Alerts />, { route: "/alerts" });
    expect(await screen.findByText(/no outbreak signals detected/i)).toBeInTheDocument();
  });
});
