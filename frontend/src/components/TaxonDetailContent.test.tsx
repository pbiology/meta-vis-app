import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/utils";
import TaxonDetailContent from "./TaxonDetailContent";

// A user whose Keycloak token carries none of the three client roles falls
// back to `reader` (see deriveRole in context/AuthContext.tsx), so the UI must
// not offer edit affordances the API would answer with a 403.
describe("TaxonDetailContent role gating", () => {
  it("hides the clinical-notes editor for a user with no client role", async () => {
    renderWithProviders(<TaxonDetailContent taxonId="42" onBack={() => {}} />, { roles: [] });

    expect(await screen.findByText("Clinical notes")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add notes" })).not.toBeInTheDocument();
  });

  it("shows the clinical-notes editor for a writer", async () => {
    renderWithProviders(<TaxonDetailContent taxonId="42" onBack={() => {}} />, {
      roles: ["writer"],
    });

    expect(await screen.findByRole("button", { name: "Add notes" })).toBeInTheDocument();
  });
});

describe("TaxonDetailContent related taxa section", () => {
  it("is hidden when the taxon is not opened from a sample", async () => {
    renderWithProviders(<TaxonDetailContent taxonId="42" onBack={() => {}} />);

    expect(await screen.findByText("Clinical notes")).toBeInTheDocument();
    expect(screen.queryByText("Related taxa in sample and controls")).not.toBeInTheDocument();
  });

  it("is shown when the sample's Mongo id is known", async () => {
    renderWithProviders(
      <TaxonDetailContent taxonId="42" sampleId="S1" sampleOid="oid-1" onBack={() => {}} />
    );

    expect(await screen.findByText("Related taxa in sample and controls")).toBeInTheDocument();
  });
});
