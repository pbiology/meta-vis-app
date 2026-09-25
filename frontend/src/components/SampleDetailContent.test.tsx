import { describe, it, expect } from "vitest";
import { missingNtcMessage } from "./SampleDetailContent";

/**
 * Without this warning the taxonomy table simply drops its NTC column, so a
 * sample ingested without a negative control looks exactly like a clean one.
 */
describe("missingNtcMessage", () => {
  it("warns when a clinical sample was declared without a control", () => {
    expect(missingNtcMessage("sample", [])).toMatch(/No negative control was declared/);
  });

  it("warns when a clinical sample carries no declaration at all", () => {
    // Ingest always writes the list, so its absence must not read as covered.
    expect(missingNtcMessage("sample", undefined)).not.toBeNull();
  });

  it("stays quiet when a control is declared", () => {
    expect(missingNtcMessage("sample", ["NTC-ELB-DNA"])).toBeNull();
  });

  it("stays quiet on controls, which are not compared against their own", () => {
    expect(missingNtcMessage("negative_ctrl", null)).toBeNull();
    expect(missingNtcMessage("positive_ctrl", [])).toBeNull();
  });
});
