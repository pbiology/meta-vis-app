import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import CaseList from "./CaseList";

const API = "*/api/v1";

// A list row is a case joined to its latest analysis, with older runs nested.
function caseRow(id: string, extra: Record<string, unknown> = {}, version = 1) {
  return {
    case: { case_id: id, notes: [] },
    latest: {
      case_id: id,
      version,
      is_latest: true,
      order_date: "2026-01-01",
      sample_count: 2,
      control_count: 0,
      analysis_type: "shotgun",
      sequencing_platform: "illumina",
      review: { reviewed: false },
      ...extra,
    },
    superseded_analyses: [],
  };
}

/** A case with an earlier, superseded analysis nested beneath its latest. */
function caseRowWithHistory(id: string) {
  const row = caseRow(id, {}, 2);
  return {
    ...row,
    superseded_analyses: [
      {
        case_id: id,
        version: 1,
        is_latest: false,
        order_date: "2025-12-01",
        sample_count: 2,
        control_count: 0,
        analysis_type: "shotgun",
        sequencing_platform: "illumina",
        review: { reviewed: true, reviewed_by: "alice" },
      },
    ],
  };
}

describe("CaseList", () => {
  it("renders rows returned by the API", async () => {
    server.use(
      http.get(`${API}/cases`, () =>
        HttpResponse.json({
          items: [caseRow("CASE-1"), caseRow("CASE-2", { review: { reviewed: true } })],
          total: 2,
          pages: 1,
          ticket_links_enabled: false,
        })
      )
    );

    renderWithProviders(<CaseList />, { route: "/cases" });

    await waitFor(() => {
      expect(screen.getByText("CASE-1")).toBeInTheDocument();
      expect(screen.getByText("CASE-2")).toBeInTheDocument();
    });
  });

  it("submitting the search form refetches with ?search=", async () => {
    let searchSeen = "";
    server.use(
      http.get(`${API}/cases`, ({ request }) => {
        searchSeen = new URL(request.url).searchParams.get("search") ?? "";
        return HttpResponse.json({ items: [], total: 0, pages: 1 });
      })
    );

    renderWithProviders(<CaseList />, { route: "/cases" });
    await waitFor(() =>
      expect(screen.getByPlaceholderText(/search case name/i)).toBeInTheDocument()
    );

    await userEvent.type(screen.getByPlaceholderText(/search case name/i), "ACME{enter}");
    await waitFor(() => expect(searchSeen).toBe("ACME"));
  });

  it("clicking the Pending filter sets reviewed=pending on the request", async () => {
    let reviewedSeen = "";
    server.use(
      http.get(`${API}/cases`, ({ request }) => {
        reviewedSeen = new URL(request.url).searchParams.get("reviewed") ?? "";
        return HttpResponse.json({ items: [], total: 0, pages: 1 });
      })
    );

    renderWithProviders(<CaseList />, { route: "/cases" });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Pending" })).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole("button", { name: "Pending" }));
    await waitFor(() => expect(reviewedSeen).toBe("pending"));
  });

  it("admin can delete a case via the confirmation modal", async () => {
    let deleted = false;
    server.use(
      http.get(`${API}/cases`, () =>
        HttpResponse.json({ items: [caseRow("CASE-X")], total: 1, pages: 1 })
      ),
      http.delete(`${API}/cases/CASE-X`, () => {
        deleted = true;
        return HttpResponse.json({});
      })
    );

    renderWithProviders(<CaseList />, { route: "/cases" });
    const row = await screen.findByText("CASE-X");
    const tr = row.closest("tr") as HTMLElement;

    await userEvent.click(within(tr).getByRole("button", { name: "Delete" }));
    expect(screen.getByText(/delete case\?/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /delete case$/i }));
    await waitFor(() => expect(deleted).toBe(true));
  });

  it("collapses superseded analyses until the row is expanded", async () => {
    server.use(
      http.get(`${API}/cases`, () =>
        HttpResponse.json({
          items: [caseRowWithHistory("CASE-9")],
          total: 1,
          pages: 1,
          ticket_links_enabled: false,
        })
      )
    );

    renderWithProviders(<CaseList />, { route: "/cases" });

    // One row per clinical case. The current run carries no badge — only
    // superseded runs are labelled, and they are hidden until expanded.
    await waitFor(() => expect(screen.getByText("CASE-9")).toBeInTheDocument());
    expect(screen.queryByText("v1")).not.toBeInTheDocument();
    expect(screen.queryByText("v2")).not.toBeInTheDocument();
    expect(screen.queryByText("superseded")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /show earlier analyses/i }));

    // The earlier run appears, badged and keeping its own review status.
    expect(await screen.findByText("v1")).toBeInTheDocument();
    expect(screen.getByText("superseded")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    // Still nothing on the current run.
    expect(screen.queryByText("v2")).not.toBeInTheDocument();
  });

  it("renders the empty state when no cases match", async () => {
    renderWithProviders(<CaseList />, { route: "/cases" });
    expect(await screen.findByText(/no cases found/i)).toBeInTheDocument();
  });

  it("renders an error message when the cases endpoint 500s", async () => {
    server.use(http.get(`${API}/cases`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<CaseList />, { route: "/cases" });
    expect(await screen.findByText(/failed to load cases/i)).toBeInTheDocument();
  });

  it("polls every 30s — verified by advancing fake timers", async () => {
    vi.useFakeTimers();
    let calls = 0;
    server.use(
      http.get(`${API}/cases`, () => {
        calls += 1;
        return HttpResponse.json({ items: [], total: 0, pages: 1 });
      })
    );

    // React Query's background refetches trigger state updates that aren't
    // wrapped in act() by the test — the assertion below verifies the polling
    // behaviour itself; suppress the noisy act() warnings here.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      renderWithProviders(<CaseList />, { route: "/cases" });
      await vi.waitFor(() => expect(calls).toBeGreaterThanOrEqual(1));
      const before = calls;
      vi.advanceTimersByTime(30_000);
      await vi.waitFor(() => expect(calls).toBeGreaterThan(before));
    } finally {
      vi.useRealTimers();
      errSpy.mockRestore();
    }
  });
});
