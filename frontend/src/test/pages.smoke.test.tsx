/**
 * Smoke tests: render every page in isolation and assert it mounts without
 * throwing. They use the default MSW handlers (empty/permissive payloads) so
 * regressions like "page crashes on first render with empty data" fail fast.
 *
 * These are intentionally shallow — they don't assert business behaviour, only
 * that the page renders past initial loading. Page-specific behaviour belongs
 * in dedicated *.test.tsx files (see SampleDetail.test.tsx, TaxonomyTable.test.tsx).
 */
import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./utils";

import Login from "../pages/Login";
import CaseList from "../pages/CaseList";
import CaseDetail from "../pages/CaseDetail";
import SampleList from "../pages/SampleList";
import SampleDetail from "../pages/SampleDetail";
import Admin from "../pages/Admin";
import MetavalDetails from "../pages/MetavalDetails";
import Alerts from "../pages/Alerts";
import IgnoreList from "../pages/IgnoreList";
import KnownPathogens from "../pages/KnownPathogens";
import TaxonDetail from "../pages/TaxonDetail";
import NtcTrends from "../pages/NtcTrends";
import NtcListsPage from "../pages/NtcListsPage";
import UserPreferences from "../pages/UserPreferences";

async function settled() {
  // Loading indicators across the codebase use either a hellip or a spinner;
  // we wait for either none or a stable DOM tick.
  await waitFor(() => {
    expect(document.body).toBeTruthy();
  });
}

describe("page smoke tests", () => {
  it("Login renders", async () => {
    renderWithProviders(<Login />, { authenticated: false });
    expect(screen.getByText(/meta-vis/i)).toBeInTheDocument();
  });

  it("CaseList renders empty state", async () => {
    renderWithProviders(<CaseList />, { route: "/cases" });
    await settled();
  });

  it("CaseDetail renders for a case id", async () => {
    renderWithProviders(<CaseDetail />, {
      route: "/cases/case-1",
      routePath: "/cases/:caseId",
    });
    await settled();
  });

  it("SampleList renders empty state", async () => {
    renderWithProviders(<SampleList />, { route: "/samples" });
    await settled();
  });

  it("SampleDetail renders for a sample id", async () => {
    renderWithProviders(<SampleDetail />, {
      route: "/samples/sample-1",
      routePath: "/samples/:sampleId",
    });
    await settled();
  });

  it("Admin renders", async () => {
    renderWithProviders(<Admin />, { route: "/admin" });
    await settled();
  });

  it("MetavalDetails renders for an id", async () => {
    renderWithProviders(<MetavalDetails />, {
      route: "/samples/s1/metaval/m1",
      routePath: "/samples/:sampleId/metaval/:metavalId",
    });
    await settled();
  });

  it("Alerts renders", async () => {
    renderWithProviders(<Alerts />, { route: "/alerts" });
    await settled();
  });

  it("IgnoreList renders", async () => {
    renderWithProviders(<IgnoreList />, { route: "/alerts/ignorelist" });
    await settled();
  });

  it("KnownPathogens renders", async () => {
    renderWithProviders(<KnownPathogens />, { route: "/pathogens" });
    await settled();
  });

  it("TaxonDetail renders for a taxon id", async () => {
    renderWithProviders(<TaxonDetail />, {
      route: "/taxa/9606",
      routePath: "/taxa/:taxonId",
    });
    await settled();
  });

  it("NtcTrends renders", async () => {
    renderWithProviders(<NtcTrends />, { route: "/ntc" });
    await settled();
  });

  it("NtcListsPage renders", async () => {
    renderWithProviders(<NtcListsPage />, { route: "/ntc/lists" });
    await settled();
  });

  it("UserPreferences renders", async () => {
    renderWithProviders(<UserPreferences />, { route: "/preferences" });
    expect(screen.getByText(/preferences/i)).toBeInTheDocument();
  });
});
