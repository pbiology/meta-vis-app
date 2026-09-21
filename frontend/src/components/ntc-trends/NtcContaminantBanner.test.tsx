import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import NtcContaminantBanner from "./NtcContaminantBanner";

describe("NtcContaminantBanner", () => {
  it("renders nothing when there are no alerts", () => {
    const { container } = renderWithProviders(<NtcContaminantBanner alerts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists each alert with its counts and threshold", () => {
    renderWithProviders(
      <NtcContaminantBanner
        alerts={[
          {
            taxon_id: 1,
            taxon_name: "Cutibacterium-acnes",
            control_count: 2,
            case_count: 3,
            min_reads: 5,
          },
          {
            taxon_id: 2,
            taxon_name: "Staphylococcus-epidermidis",
            control_count: 1,
            case_count: 1,
            min_reads: 10,
          },
        ]}
      />
    );
    expect(screen.getByText("Cutibacterium acnes")).toBeInTheDocument();
    expect(screen.getByText("2 NTCs")).toBeInTheDocument();
    expect(screen.getByText("3 cases affected")).toBeInTheDocument();
    expect(screen.getByText("Staphylococcus epidermidis")).toBeInTheDocument();
    expect(screen.getByText("1 NTC")).toBeInTheDocument();
    expect(screen.getByText("1 case affected")).toBeInTheDocument();
  });

  it("separates how recurrent a contaminant is from how many cases it touched", () => {
    // One contaminated control sequenced alongside five cases is a single bad
    // run, not five independent detections.
    renderWithProviders(
      <NtcContaminantBanner
        alerts={[
          {
            taxon_id: 1,
            taxon_name: "Ralstonia-pickettii",
            control_count: 1,
            case_count: 5,
            min_reads: 3,
          },
        ]}
      />
    );
    expect(screen.getByText("1 NTC")).toBeInTheDocument();
    expect(screen.getByText("5 cases affected")).toBeInTheDocument();
  });
});
