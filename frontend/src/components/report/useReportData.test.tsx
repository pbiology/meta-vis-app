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

// A two-sample case (DNA + RNA) with two classifiers in DNA and one in RNA.
// HIV-1 (taxon 11676) is in the kraken2 profile of both samples; E. coli (562)
// is only in the DNA sample's kraken2 profile.
function seedTwoSampleCase() {
  server.use(
    // GET /cases/{id} returns identity, the analysis being viewed, and every
    // analysis of the case; the report flattens the first two.
    http.get(`${API}/cases/case-1`, () =>
      HttpResponse.json({
        case: {
          case_id: "case-1",
          subject_id: "subj-1",
          notes: [{ id: "n1", text: "A note", author: "a", created_at: "2026-04-29" }],
        },
        analysis: { case_id: "case-1", version: 1, is_latest: true },
        analyses: [{ case_id: "case-1", version: 1, is_latest: true }],
      })
    ),
    http.get(`${API}/cases/case-1/samples`, () =>
      HttpResponse.json([
        // RNA listed first to verify ordering reshuffles to DNA-before-RNA.
        {
          _id: "mongo-rna",
          sample_id: "S001-RNA",
          case_id: "case-1",
          sample_type: "RNA",
          material: "RNA",
          subject_id: "subj-1",
        },
        {
          _id: "mongo-dna",
          sample_id: "S001-DNA",
          case_id: "case-1",
          sample_type: "DNA",
          material: "DNA",
          subject_id: "subj-1",
        },
      ])
    ),
    http.get(`${API}/samples/mongo-dna/profile`, () =>
      HttpResponse.json({
        profiles: [
          {
            classifier: "kraken2",
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
          {
            classifier: "bracken",
            profile: [
              {
                taxon_id: 11676,
                name: "HIV-1",
                rank: "species",
                superkingdom: "Viruses",
                abundance: 50,
              },
            ],
          },
        ],
      })
    ),
    http.get(`${API}/samples/mongo-rna/profile`, () =>
      HttpResponse.json({
        profiles: [
          {
            classifier: "kraken2",
            profile: [
              {
                taxon_id: 11676,
                name: "HIV-1",
                rank: "species",
                superkingdom: "Viruses",
                abundance: 30,
              },
            ],
          },
        ],
      })
    ),
    http.get(`${API}/alerts/pathogens`, () =>
      HttpResponse.json([{ taxon_id: 11676, taxon_name: "HIV-1", reason: null }])
    ),
    http.get(`${API}/subjects/subj-1`, () => HttpResponse.json({ subject_id: "subj-1", sex: "F" }))
  );
}

describe("useReportData (case-scoped)", () => {
  it("orders samples DNA-before-RNA regardless of API order", async () => {
    seedTwoSampleCase();
    const { result } = renderHook(
      () => useReportData("case-1", { "S001-DNA": [11676], "S001-RNA": [11676] }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.samples.map((s) => s.sample_id)).toEqual(["S001-DNA", "S001-RNA"]);
  });

  it("collects classifiers from all samples, alphabetically", async () => {
    seedTwoSampleCase();
    const { result } = renderHook(() => useReportData("case-1", { "S001-DNA": [11676] }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.classifiers).toEqual(["bracken", "kraken2"]);
  });

  it("builds per-(sample, classifier) cells with reads + pct, omitting missing detections", async () => {
    seedTwoSampleCase();
    const { result } = renderHook(
      () => useReportData("case-1", { "S001-DNA": [11676, 562], "S001-RNA": [11676] }),
      { wrapper: makeWrapper() }
    );
    await waitFor(() => expect(result.current.data).toBeDefined());
    const data = result.current.data!;

    const hiv = data.taxa.find((t) => t.taxon_id === 11676)!;
    // DNA sample: kraken2 100 / (100+900) = 10%; bracken 50 / 50 = 100%
    expect(hiv.cells["S001-DNA"].kraken2).toEqual({ reads: 100, pct: 10 });
    expect(hiv.cells["S001-DNA"].bracken).toEqual({ reads: 50, pct: 100 });
    // RNA sample: kraken2 30 / 30 = 100%; bracken absent → key missing
    expect(hiv.cells["S001-RNA"].kraken2).toEqual({ reads: 30, pct: 100 });
    expect(hiv.cells["S001-RNA"].bracken).toBeUndefined();

    const ecoli = data.taxa.find((t) => t.taxon_id === 562)!;
    expect(ecoli.cells["S001-DNA"].kraken2).toEqual({ reads: 900, pct: 90 });
    expect(ecoli.cells["S001-RNA"]).toBeUndefined();
  });

  it("flags pathogens and resolves the case subject", async () => {
    seedTwoSampleCase();
    const { result } = renderHook(() => useReportData("case-1", { "S001-DNA": [11676] }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    const data = result.current.data!;
    expect(data.taxa[0].pathogen).toBe(true);
    expect(data.subject?.subject_id).toBe("subj-1");
  });

  it("returns no taxa when selections are empty", async () => {
    seedTwoSampleCase();
    const { result } = renderHook(() => useReportData("case-1", {}), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.taxa).toEqual([]);
  });
});
