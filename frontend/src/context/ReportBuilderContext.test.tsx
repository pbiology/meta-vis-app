import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { ReactNode } from "react";
import { ReportBuilderProvider, useReportBuilder } from "./ReportBuilderContext";

const STORAGE_KEY = "report-builder";

function wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return <ReportBuilderProvider>{children}</ReportBuilderProvider>;
}

beforeEach(() => {
  sessionStorage.clear();
});

describe("ReportBuilderContext", () => {
  it("starts empty for any sample", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    expect(result.current.selectedFor("S1")).toEqual([]);
    expect(result.current.isSelected("S1", 42)).toBe(false);
  });

  it("adds taxa and dedupes", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    act(() => {
      result.current.addTaxon("S1", 11676);
      result.current.addTaxon("S1", 9606);
      result.current.addTaxon("S1", 11676); // duplicate
    });
    expect(result.current.selectedFor("S1")).toEqual([11676, 9606]);
    expect(result.current.isSelected("S1", 11676)).toBe(true);
  });

  it("isolates selections between samples", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    act(() => {
      result.current.addTaxon("S1", 1);
      result.current.addTaxon("S2", 2);
    });
    expect(result.current.selectedFor("S1")).toEqual([1]);
    expect(result.current.selectedFor("S2")).toEqual([2]);
  });

  it("removes a taxon and drops empty sample keys", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    act(() => {
      result.current.addTaxon("S1", 1);
      result.current.addTaxon("S1", 2);
      result.current.removeTaxon("S1", 1);
    });
    expect(result.current.selectedFor("S1")).toEqual([2]);

    act(() => {
      result.current.removeTaxon("S1", 2);
    });
    expect(result.current.selectedFor("S1")).toEqual([]);
    // After all taxa for a sample are removed, the key should not be persisted.
    const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored).not.toHaveProperty("S1");
  });

  it("clear removes all taxa for one sample but leaves others", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    act(() => {
      result.current.addTaxon("S1", 1);
      result.current.addTaxon("S2", 2);
      result.current.clear("S1");
    });
    expect(result.current.selectedFor("S1")).toEqual([]);
    expect(result.current.selectedFor("S2")).toEqual([2]);
  });

  it("persists to sessionStorage", () => {
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    act(() => {
      result.current.addTaxon("S1", 11676);
    });
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!)).toEqual({ S1: [11676] });
  });

  it("rehydrates from sessionStorage on mount", () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ S1: [11676, 9606] }));
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    expect(result.current.selectedFor("S1")).toEqual([11676, 9606]);
  });

  it("ignores malformed sessionStorage payloads", () => {
    sessionStorage.setItem(STORAGE_KEY, "not-json");
    const { result } = renderHook(() => useReportBuilder(), { wrapper });
    expect(result.current.selectedFor("S1")).toEqual([]);
  });

  it("throws when used outside the provider", () => {
    // Suppress React's expected error log for the throw.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useReportBuilder())).toThrow(
      /useReportBuilder must be used inside ReportBuilderProvider/
    );
    spy.mockRestore();
  });
});
