import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import CaseList from "./CaseList";

describe("CaseList", () => {
  it("renders nothing without cases", () => {
    const { container } = renderWithProviders(<CaseList />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for an empty list", () => {
    const { container } = renderWithProviders(<CaseList caseIds={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a single case on its own, without a count", () => {
    renderWithProviders(<CaseList caseIds={["greencheetah"]} />);

    expect(screen.getByText("greencheetah")).toBeInTheDocument();
    expect(screen.queryByText(/cases:/)).not.toBeInTheDocument();
  });

  it("counts the cases when one control covers several", () => {
    renderWithProviders(<CaseList caseIds={["deardonkey", "dualwombat"]} />);

    expect(screen.getByText(/2 cases: deardonkey, dualwombat/)).toBeInTheDocument();
  });

  it("truncates a long list but keeps the full count visible", () => {
    renderWithProviders(<CaseList caseIds={["aa", "bb", "cc", "dd", "ee", "ff", "gg"]} />);

    expect(screen.getByText(/7 cases: aa, bb, cc \+4/)).toBeInTheDocument();
  });
});
