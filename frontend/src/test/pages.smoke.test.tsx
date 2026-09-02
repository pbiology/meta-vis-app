/**
 * Smoke tests: render every page in isolation and assert it mounts, finishes
 * loading, and shows its own heading. They use the default MSW handlers
 * (empty/permissive payloads) so regressions like "page crashes on first render
 * with empty data" fail fast.
 *
 * These are intentionally shallow — they don't assert business behaviour, only
 * that the page renders past initial loading. Page-specific behaviour belongs
 * in dedicated *.test.tsx files (see SampleDetail.test.tsx, TaxonomyTable.test.tsx).
 *
 * The assertions are deliberately more than a mount check. An earlier version
 * waited on `document.body` being truthy, which a page that throws during
 * render still satisfies — a stale case fixture crashed CaseView while this
 * suite reported green, and the failure surfaced only as a file-level unhandled
 * error. Every case now names something the page must actually put on screen.
 */
import { describe, it, expect } from "vitest";
import type { ReactElement } from "react";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./utils";

import Login from "../pages/Login";
import CaseList from "../pages/CaseList";
import CaseView from "../pages/CaseView";
import SampleList from "../pages/SampleList";
import SampleDetail from "../pages/SampleDetail";
import MetavalDetails from "../pages/MetavalDetails";
import Alerts from "../pages/Alerts";
import IgnoreList from "../pages/IgnoreList";
import KnownPathogens from "../pages/KnownPathogens";
import KnownPathogensPanel from "../components/KnownPathogensPanel";
import TaxonDetail from "../pages/TaxonDetail";
import NtcTrends from "../pages/NtcTrends";
import NtcListsPage from "../pages/NtcListsPage";
import UserPreferences from "../pages/UserPreferences";

type RenderOpts = Parameters<typeof renderWithProviders>[1];

/**
 * Render a page and assert it got past loading with content on screen.
 *
 * `heading` is the page's own landmark, which is what distinguishes "rendered"
 * from "rendered a spinner forever" or "threw and unmounted". Pages share a
 * loading vocabulary ("Loading…"), so waiting for that to clear works
 * uniformly; the non-empty check covers a throw, since React unmounts the tree
 * (and the test error boundary in utils.tsx renders nothing in its place).
 */
async function expectPageRenders(
  ui: ReactElement,
  heading: string | RegExp,
  opts: RenderOpts = {}
) {
  const { container } = renderWithProviders(ui, opts);
  await waitFor(() => expect(screen.queryAllByText(/^loading/i)).toHaveLength(0));
  expect(container).not.toBeEmptyDOMElement();
  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
}

describe("page smoke tests", () => {
  it("Login renders", async () => {
    await expectPageRenders(<Login />, "meta-vis", { authenticated: false });
  });

  it("CaseList renders empty state", async () => {
    await expectPageRenders(<CaseList />, "Cases", { route: "/cases" });
  });

  it("CaseView renders for a case id", async () => {
    await expectPageRenders(<CaseView />, "case-1", {
      route: "/case/case-1",
      routePath: "/case/:caseId",
    });
  });

  it("CaseView renders for a specific analysis version", async () => {
    await expectPageRenders(<CaseView />, "case-1", {
      route: "/case/case-1/analyses/2",
      routePath: "/case/:caseId/analyses/:version",
    });
  });

  it("SampleList renders empty state", async () => {
    await expectPageRenders(<SampleList />, "All samples", { route: "/samples" });
  });

  it("SampleDetail renders for a sample id", async () => {
    await expectPageRenders(<SampleDetail />, "sample-1", {
      route: "/samples/sample-1",
      routePath: "/samples/:sampleId",
    });
  });

  it("MetavalDetails renders for an id", async () => {
    await expectPageRenders(<MetavalDetails />, "Test taxon", {
      route: "/samples/s1/metaval/m1",
      routePath: "/samples/:sampleId/metaval/:metavalId",
    });
  });

  it("Alerts renders", async () => {
    await expectPageRenders(<Alerts />, "Outbreak alerts", { route: "/alerts" });
  });

  it("IgnoreList renders", async () => {
    await expectPageRenders(<IgnoreList />, "Ignored taxa", { route: "/alerts/ignorelist" });
  });

  it("KnownPathogens renders", async () => {
    await expectPageRenders(<KnownPathogens />, "Known pathogens", { route: "/pathogens" });
  });

  it("KnownPathogensPanel renders with case taxa", async () => {
    await expectPageRenders(<KnownPathogensPanel samples={[]} pathogenMap={{}} />, /pathogen/i, {
      route: "/",
    });
  });

  it("TaxonDetail renders for a taxon id", async () => {
    await expectPageRenders(<TaxonDetail />, "Test taxon", {
      route: "/taxa/9606",
      routePath: "/taxa/:taxonId",
    });
  });

  it("NtcTrends renders", async () => {
    await expectPageRenders(<NtcTrends />, "Kingdom breakdown", { route: "/ntc" });
  });

  it("NtcListsPage renders", async () => {
    await expectPageRenders(<NtcListsPage />, "NTC lists", { route: "/ntc/lists" });
  });

  it("UserPreferences renders", async () => {
    await expectPageRenders(<UserPreferences />, "Preferences", { route: "/preferences" });
  });
});
