import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import SampleList from "./SampleList";

const API = "*/api/v1";

describe("SampleList", () => {
  it("renders sample rows", async () => {
    server.use(
      http.get(`${API}/samples`, () =>
        HttpResponse.json({
          items: [
            { _id: "s1", sample_id: "SAMPLE-1", sample_type: "sample", case_id: "C1" },
            { _id: "s2", sample_id: "SAMPLE-2", sample_type: "control", case_id: "C2" },
          ],
          total: 2,
          pages: 1,
          page: 1,
        })
      )
    );

    renderWithProviders(<SampleList />, { route: "/samples" });
    await waitFor(() => {
      expect(screen.getByText("SAMPLE-1")).toBeInTheDocument();
      expect(screen.getByText("SAMPLE-2")).toBeInTheDocument();
    });
  });

  it("filter pill 'Controls' refetches with filter=controls", async () => {
    let filterSeen = "";
    server.use(
      http.get(`${API}/samples`, ({ request }) => {
        filterSeen = new URL(request.url).searchParams.get("filter") ?? "";
        return HttpResponse.json({ items: [], total: 0, pages: 1, page: 1 });
      })
    );

    renderWithProviders(<SampleList />, { route: "/samples" });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Controls" })).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole("button", { name: "Controls" }));
    await waitFor(() => expect(filterSeen).toBe("controls"));
  });

  it("submitting the search form refetches with ?search=", async () => {
    let searchSeen = "";
    server.use(
      http.get(`${API}/samples`, ({ request }) => {
        searchSeen = new URL(request.url).searchParams.get("search") ?? "";
        return HttpResponse.json({ items: [], total: 0, pages: 1, page: 1 });
      })
    );

    renderWithProviders(<SampleList />, { route: "/samples" });
    await userEvent.type(await screen.findByPlaceholderText(/search sample id/i), "MX-9{enter}");
    await waitFor(() => expect(searchSeen).toBe("MX-9"));
  });

  it("renders the empty state when no samples match", async () => {
    renderWithProviders(<SampleList />, { route: "/samples" });
    expect(await screen.findByText(/no samples match this filter/i)).toBeInTheDocument();
  });

  it("renders an error message when the samples endpoint 500s", async () => {
    server.use(http.get(`${API}/samples`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<SampleList />, { route: "/samples" });
    expect(await screen.findByText(/failed to load samples/i)).toBeInTheDocument();
  });
});
