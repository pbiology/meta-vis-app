import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import CaseView from "./CaseView";

const API = "*/api/v1";

const V1 = { case_id: "CASE-1", version: 1, is_latest: false, order_date: "2026-07-01" };
const V2 = { case_id: "CASE-1", version: 2, is_latest: true, order_date: "2026-08-01" };

/** Records which review endpoint the UI actually called. */
let reviewedPath: string | null;

beforeEach(() => {
  reviewedPath = null;
  server.use(
    // Versioned detail — the run being viewed is the superseded v1.
    http.get(`${API}/cases/:caseId/analyses/:version`, ({ params }) =>
      HttpResponse.json({
        case: { case_id: params.caseId, notes: [] },
        analysis: { ...V1, review: { reviewed: false } },
        analyses: [V2, V1],
      })
    ),
    http.get(`${API}/cases/:caseId/analyses/:version/samples`, () => HttpResponse.json([])),

    // Both review routes are registered so the test can tell them apart:
    // hitting the bare one means the version was dropped somewhere.
    http.patch(`${API}/cases/:caseId/analyses/:version/review`, ({ request }) => {
      reviewedPath = new URL(request.url).pathname;
      return HttpResponse.json({});
    }),
    http.patch(`${API}/cases/:caseId/review`, ({ request }) => {
      reviewedPath = new URL(request.url).pathname;
      return HttpResponse.json({});
    })
  );
});

describe("CaseView review targeting", () => {
  it("marks the analysis being viewed reviewed, not the case's latest", async () => {
    renderWithProviders(<CaseView />, {
      route: "/case/CASE-1/analyses/1",
      routePath: "/case/:caseId/analyses/:version",
    });

    const button = await screen.findByRole("button", { name: /mark reviewed/i });
    await userEvent.click(button);

    // Without the version the request resolves to is_latest server-side, which
    // would review v2 while the user is looking at v1.
    await waitFor(() => expect(reviewedPath).not.toBeNull());
    expect(reviewedPath).toBe("/api/v1/cases/CASE-1/analyses/1/review");
  });

  it("names the superseded run in the tab title", async () => {
    renderWithProviders(<CaseView />, {
      route: "/case/CASE-1/analyses/1",
      routePath: "/case/:caseId/analyses/:version",
    });

    await waitFor(() => expect(document.title).toBe("CASE-1 (v1) — meta-vis"));
  });

  it("targets the latest analysis on the unversioned route", async () => {
    server.use(
      http.get(`${API}/cases/:caseId`, ({ params }) =>
        HttpResponse.json({
          case: { case_id: params.caseId, notes: [] },
          analysis: { ...V2, review: { reviewed: false } },
          analyses: [V2, V1],
        })
      ),
      http.get(`${API}/cases/:caseId/samples`, () => HttpResponse.json([]))
    );

    renderWithProviders(<CaseView />, {
      route: "/case/CASE-1",
      routePath: "/case/:caseId",
    });

    const button = await screen.findByRole("button", { name: /mark reviewed/i });
    await userEvent.click(button);

    await waitFor(() => expect(reviewedPath).not.toBeNull());
    expect(reviewedPath).toBe("/api/v1/cases/CASE-1/review");
  });

  it("shows a new comment without a page refresh", async () => {
    const notes: Array<Record<string, unknown>> = [];
    server.use(
      // Detail re-reads the note thread, so a correct invalidation shows the
      // new comment; a missed one leaves the list stale until a reload.
      http.get(`${API}/cases/:caseId/analyses/:version`, ({ params }) =>
        HttpResponse.json({
          case: { case_id: params.caseId, notes: [...notes] },
          analysis: { ...V1, review: { reviewed: false } },
          analyses: [V2, V1],
        })
      ),
      http.post(`${API}/cases/:caseId/notes`, async ({ request }) => {
        const body = (await request.json()) as { text: string };
        const note = {
          id: `n${notes.length + 1}`,
          text: body.text,
          author: "tester",
          created_at: new Date().toISOString(),
        };
        notes.push(note);
        return HttpResponse.json(note);
      })
    );

    renderWithProviders(<CaseView />, {
      route: "/case/CASE-1/analyses/1",
      routePath: "/case/:caseId/analyses/:version",
    });

    // "Comments" appears both in the case sidebar and as a jump link on the
    // overview; scope to the sidebar so the query is unambiguous.
    const sidebar = await screen.findByRole("complementary");
    await userEvent.click(within(sidebar).getByRole("button", { name: /comments/i }));
    const box = await screen.findByRole("textbox");
    await userEvent.type(box, "contamination or real?");
    await userEvent.click(screen.getByRole("button", { name: /add comment/i }));

    expect(await screen.findByText("contamination or real?")).toBeInTheDocument();
  });

  it("marks the current run '(latest)' in the tab title, even with one analysis", async () => {
    server.use(
      http.get(`${API}/cases/:caseId`, ({ params }) =>
        HttpResponse.json({
          case: { case_id: params.caseId, notes: [] },
          // A case that has never been re-sequenced still gets the marker.
          analysis: { ...V2, version: 1, review: { reviewed: false } },
          analyses: [{ ...V2, version: 1 }],
        })
      ),
      http.get(`${API}/cases/:caseId/samples`, () => HttpResponse.json([]))
    );

    renderWithProviders(<CaseView />, {
      route: "/case/CASE-1",
      routePath: "/case/:caseId",
    });

    await waitFor(() => expect(document.title).toBe("CASE-1 (latest) — meta-vis"));
  });
});
