import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import NtcFiltersBar, { type NtcPipelineOption } from "./NtcFiltersBar";

const PIPELINES: NtcPipelineOption[] = [
  { value: "taxprofiler", label: "Taxprofiler" },
  { value: "trana", label: "Trana" },
];

function renderBar(overrides: Partial<Parameters<typeof NtcFiltersBar>[0]> = {}) {
  const props = {
    material: "DNA",
    pipeline: "taxprofiler",
    windowDays: 90,
    minReads: 3,
    minAbundance: 0.001,
    minCasePct: 10,
    availablePipelines: PIPELINES,
    onMaterialChange: vi.fn(),
    onPipelineChange: vi.fn(),
    onWindowDaysChange: vi.fn(),
    onMinReadsChange: vi.fn(),
    onMinAbundanceChange: vi.fn(),
    onMinCasePctChange: vi.fn(),
    ...overrides,
  };
  renderWithProviders(<NtcFiltersBar {...props} />);
  return props;
}

describe("NtcFiltersBar", () => {
  it("clicking a window pill calls onWindowDaysChange with the new value", async () => {
    const props = renderBar();
    await userEvent.click(screen.getByRole("button", { name: "30d" }));
    expect(props.onWindowDaysChange).toHaveBeenCalledWith(30);
  });

  it("hides the DNA/RNA toggle when pipeline is trana (amplicon)", () => {
    renderBar({ pipeline: "trana" });
    expect(screen.queryByRole("button", { name: "DNA" })).not.toBeInTheDocument();
  });

  it("shows abundance dropdown when pipeline is trana, reads dropdown otherwise", () => {
    const { rerender } = renderWithProviders(
      <NtcFiltersBar
        material="DNA"
        pipeline="taxprofiler"
        windowDays={90}
        minReads={3}
        minAbundance={0.001}
        minCasePct={10}
        availablePipelines={PIPELINES}
        onMaterialChange={vi.fn()}
        onPipelineChange={vi.fn()}
        onWindowDaysChange={vi.fn()}
        onMinReadsChange={vi.fn()}
        onMinAbundanceChange={vi.fn()}
        onMinCasePctChange={vi.fn()}
      />
    );
    expect(screen.getByText(/min reads/i)).toBeInTheDocument();
    rerender(
      <NtcFiltersBar
        material="DNA"
        pipeline="trana"
        windowDays={90}
        minReads={3}
        minAbundance={0.001}
        minCasePct={10}
        availablePipelines={PIPELINES}
        onMaterialChange={vi.fn()}
        onPipelineChange={vi.fn()}
        onWindowDaysChange={vi.fn()}
        onMinReadsChange={vi.fn()}
        onMinAbundanceChange={vi.fn()}
        onMinCasePctChange={vi.fn()}
      />
    );
    expect(screen.getByText(/min abundance/i)).toBeInTheDocument();
  });
});
