import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import NtcContaminantBanner from "./NtcContaminantBanner";

describe("NtcContaminantBanner", () => {
  it("renders nothing when there are no alerts", () => {
    const { container } = renderWithProviders(<NtcContaminantBanner alerts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists each alert with case count and threshold", () => {
    renderWithProviders(
      <NtcContaminantBanner
        alerts={[
          { taxon_id: 1, taxon_name: "Cutibacterium-acnes", case_count: 3, min_reads: 5 },
          { taxon_id: 2, taxon_name: "Staphylococcus-epidermidis", case_count: 1, min_reads: 10 },
        ]}
      />
    );
    expect(screen.getByText("Cutibacterium acnes")).toBeInTheDocument();
    expect(screen.getByText("3 cases")).toBeInTheDocument();
    expect(screen.getByText("Staphylococcus epidermidis")).toBeInTheDocument();
    expect(screen.getByText("1 case")).toBeInTheDocument();
  });
});
