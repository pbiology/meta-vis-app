import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { useReportData } from "./useReportData";

const API = "*/api/v1";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useReportData", () => {
  it("assembles report data from sample, profile, case, pathogens, subject", async () => {
    server.use(
      http.get(`${API}/samples/sample-1`, () =>
        HttpResponse.json({
          sample_id: "sample-1",
          case_id: "case-1",
          subject_id: "subj-1",
          sample_type: "sample",
          material: "DNA",
        })
      ),
      http.get(`${API}/samples/sample-1/profile`, () =>
        HttpResponse.json({
          profiles: [
            {
              classifier: "kraken2",
              classifier_db: "k2-standard",
              profile: [
                {
                  taxon_id: 11676,
                  name: "HIV-1",
                  rank: "species",
                  superkingdom: "Viruses",
                  abundance: 100,
                },
                {
                  taxon_id: 562,
                  name: "Escherichia coli",
                  rank: "species",
                  superkingdom: "Bacteria",
                  abundance: 900,
                },
              ],
            },
          ],
        })
      ),
      http.get(`${API}/cases/case-1`, () =>
        HttpResponse.json({
          case_id: "case-1",
          notes: [{ id: "n1", text: "A note", author: "a", created_at: "2026-04-29" }],
        })
      ),
      http.get(`${API}/alerts/pathogens`, () =>
        HttpResponse.json([{ taxon_id: 11676, taxon_name: "HIV-1", reason: null }])
      ),
      http.get(`${API}/subjects/subj-1`, () =>
        HttpResponse.json({ subject_id: "subj-1", sex: "F" })
      )
    );

    const { result } = renderHook(() => useReportData("sample-1", [11676]), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    const data = result.current.data!;

    expect(data.sample.sample_id).toBe("sample-1");
    expect(data.subject?.subject_id).toBe("subj-1");
    expect(data.notes).toHaveLength(1);
    expect(data.taxa).toHaveLength(1);
    expect(data.taxa[0].name).toBe("HIV-1");
    expect(data.taxa[0].pathogen).toBe(true);
    expect(data.taxa[0].abundance.kraken2).toBe(100);
    // 100 / (100 + 900) = 10%
    expect(data.taxa[0].pct.kraken2).toBeCloseTo(10, 5);
  });

  it("returns subject = null when sample has no subject_id", async () => {
    server.use(
      http.get(`${API}/samples/sample-2`, () =>
        HttpResponse.json({ sample_id: "sample-2", case_id: "case-2", sample_type: "sample" })
      ),
      http.get(`${API}/samples/sample-2/profile`, () => HttpResponse.json({ profiles: [] })),
      http.get(`${API}/cases/case-2`, () => HttpResponse.json({ case_id: "case-2" }))
    );

    const { result } = renderHook(() => useReportData("sample-2", []), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.subject).toBeNull();
    expect(result.current.data!.taxa).toEqual([]);
  });

  it("preserves the order of taxonIds passed in", async () => {
    server.use(
      http.get(`${API}/samples/s/profile`, () =>
        HttpResponse.json({
          profiles: [
            {
              classifier: "k",
              classifier_db: "d",
              profile: [
                { taxon_id: 1, name: "first", abundance: 10 },
                { taxon_id: 2, name: "second", abundance: 20 },
                { taxon_id: 3, name: "third", abundance: 30 },
              ],
            },
          ],
        })
      ),
      http.get(`${API}/samples/s`, () => HttpResponse.json({ sample_id: "s", case_id: "c" })),
      http.get(`${API}/cases/c`, () => HttpResponse.json({ case_id: "c" }))
    );

    const { result } = renderHook(() => useReportData("s", [3, 1, 2]), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.taxa.map((t) => t.taxon_id)).toEqual([3, 1, 2]);
  });
});
