import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CaseReportPill from "./CaseReportPill";

describe("CaseReportPill", () => {
  it("renders the count", () => {
    render(<CaseReportPill count={0} onClick={() => {}} />);
    expect(screen.getByRole("button", { name: /open report/i })).toHaveTextContent("0");
  });

  it("uses singular label for one taxon in aria-label", () => {
    render(<CaseReportPill count={1} onClick={() => {}} />);
    expect(screen.getByRole("button", { name: /1 taxon selected/i })).toBeInTheDocument();
  });

  it("uses plural label for multiple taxa", () => {
    render(<CaseReportPill count={3} onClick={() => {}} />);
    expect(screen.getByRole("button", { name: /3 taxa selected/i })).toBeInTheDocument();
  });

  it("invokes onClick when pressed", () => {
    const onClick = vi.fn();
    render(<CaseReportPill count={2} onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
