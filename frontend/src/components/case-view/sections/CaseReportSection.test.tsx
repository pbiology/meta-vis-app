import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import type { Sample } from "../../../api/types";
import CaseReportSection from "./CaseReportSection";
import { renderWithProviders } from "../../../test/utils";

function makeSample(id: string): Sample {
  return { sample_id: id, case_id: "case-1" } as Sample;
}

describe("CaseReportSection", () => {
  it("shows empty state when nothing is selected", () => {
    renderWithProviders(
      <CaseReportSection caseId="case-1" samples={[makeSample("sample-1")]} version={null} />
    );
    expect(screen.getByText(/Report builder/i)).toBeInTheDocument();
    expect(screen.getByText(/No taxa selected/i)).toBeInTheDocument();
  });

  it("renders the preview header with totals when selections exist", () => {
    renderWithProviders(
      <CaseReportSection
        caseId="case-1"
        version={null}
        samples={[makeSample("sample-1"), makeSample("sample-2")]}
      />,
      {
        sessionStorage: {
          "report-builder": { "sample-1": [11676, 562], "sample-2": [9606] },
        },
      }
    );
    expect(screen.getByText(/Report preview/)).toBeInTheDocument();
    expect(screen.getByText(/3 taxa across 2 samples/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Finalise report/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Print \/ Save PDF/ })).toBeInTheDocument();
  });
});
