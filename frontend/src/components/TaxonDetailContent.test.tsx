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
