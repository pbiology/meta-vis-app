import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import CaseView from "./CaseView";

/**
 * Frontend counterpart to the backend version-isolation suite.
 *
 * The backend proves each endpoint returns the right run's data; this proves
 * the page *renders* it. Both runs carry the same sample_id and differ only in
 * their numbers, which is the configuration where reading the wrong analysis
 * becomes visible — and the one re-ingesting a fixture bundle cannot produce,
 * since those runs come out identical apart from the date.
 */

const API = "*/api/v1";

const RUNS = {
  1: { reads: 1_111_111, platform: "illumina", db: "pluspf-2024", isLatest: false },
  2: { reads: 2_222_222, platform: "nanopore", db: "pluspf-2025", isLatest: true },
} as const;

function analysisFor(version: 1 | 2) {
  const run = RUNS[version];
  return {
    case_id: "CASE-1",
    version,
    is_latest: run.isLatest,
    order_date: version === 1 ? "2026-05-01" : "2026-08-01",
    sequencing_platform: run.platform,
    classifiers: [{ name: "kraken2", db: run.db, krona_id: "kraken2" }],
    review: { reviewed: false },
    report_selections: {},
  };
}

function samplesFor(version: 1 | 2) {
  return [
    {
      _id: `mongo-v${version}`,
      sample_id: "S1", // identical in both runs, on purpose
      sample_type: "sample",
      material: "DNA",
      taxprofiler: { fastp: { total_reads_before_filtering: RUNS[version].reads } },
    },
  ];
}

beforeEach(() => {
  server.use(
    http.get(`${API}/cases/:caseId/analyses/:version`, ({ params }) => {
      const version = Number(params.version) as 1 | 2;
      return HttpResponse.json({
        case: { case_id: "CASE-1", order_date: "2026-05-01", notes: [] },
        analysis: analysisFor(version),
        analyses: [analysisFor(2), analysisFor(1)],
      });
    }),
    http.get(`${API}/cases/:caseId/analyses/:version/samples`, ({ params }) =>
      HttpResponse.json(samplesFor(Number(params.version) as 1 | 2))
    ),
    // The unversioned routes resolve to the latest run, mirroring the backend.
    // Registering them matters: without it, a page that dropped the version
    // would fail these tests by 404ing rather than by rendering v2's numbers
    // under v1's heading — which is the failure actually being guarded against.
    http.get(`${API}/cases/:caseId`, () =>
      HttpResponse.json({
        case: { case_id: "CASE-1", order_date: "2026-05-01", notes: [] },
        analysis: analysisFor(2),
        analyses: [analysisFor(2), analysisFor(1)],
      })
    ),
    http.get(`${API}/cases/:caseId/samples`, () => HttpResponse.json(samplesFor(2)))
  );
});

async function openSamples() {
  const sidebar = await screen.findByRole("complementary");
  await userEvent.click(within(sidebar).getByRole("button", { name: /^samples/i }));
}

function renderAt(version: 1 | 2) {
  renderWithProviders(<CaseView />, {
    route: `/case/CASE-1/analyses/${version}`,
    routePath: "/case/:caseId/analyses/:version",
  });
}

describe("CaseView renders the viewed run's data", () => {
  it("shows v1's read counts when viewing v1", async () => {
    renderAt(1);
    await openSamples();
    expect(await screen.findByText("1,111,111")).toBeInTheDocument();
    expect(screen.queryByText("2,222,222")).not.toBeInTheDocument();
  });

  it("shows v2's read counts when viewing v2", async () => {
    renderAt(2);
    await openSamples();
    expect(await screen.findByText("2,222,222")).toBeInTheDocument();
    expect(screen.queryByText("1,111,111")).not.toBeInTheDocument();
  });

  it("shows the superseded run's own platform on the overview", async () => {
    renderAt(1);
    // Platform lives on the analysis: a re-sequencing can legitimately switch
    // it, so reading the latest here would misreport how the run was produced.
    expect(await screen.findByText(/illumina/i)).toBeInTheDocument();
    expect(screen.queryByText(/nanopore/i)).not.toBeInTheDocument();
  });

  it("separates the case's order date from the run's", async () => {
    // v2's run date differs from the case's order date, so both are shown —
    // without this the page contradicted the case list.
    renderAt(2);
    expect(await screen.findByText("This run")).toBeInTheDocument();
  });

  it("does not show a run row when the dates agree", async () => {
    renderAt(1); // v1's order_date equals the case's
    await screen.findByRole("complementary");
    expect(screen.queryByText("This run")).not.toBeInTheDocument();
  });
});
