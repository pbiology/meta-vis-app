import { describe, expect, it } from "vitest";
import { metavalByTaxon, metavalForClassifier, unmatchedMetaval } from "./metavalMatch";
import { metavalSummary } from "../test/fixtures/samples";

describe("metavalForClassifier", () => {
  it("keeps only the given classifier's results", () => {
    const kraken = metavalSummary();
    const centrifuge = metavalSummary({ _id: "mv-c", classifier: "centrifuge" });
    expect(metavalForClassifier([kraken, centrifuge], "kraken2")).toEqual([kraken]);
  });
});

describe("metavalByTaxon", () => {
  it("keys results by taxon id and skips unresolved taxa", () => {
    const resolved = metavalSummary();
    const unresolved = metavalSummary({ _id: "mv-x", taxon_id: null });
    const byTaxon = metavalByTaxon([resolved, unresolved]);
    expect([...byTaxon.keys()]).toEqual([11676]);
    expect(byTaxon.get(11676)).toBe(resolved);
  });
});

describe("unmatchedMetaval", () => {
  it("returns results whose taxon is unresolved or not listed", () => {
    const listed = metavalSummary();
    const unresolved = metavalSummary({ _id: "mv-x", taxon_id: null });
    const absent = metavalSummary({ _id: "mv-y", taxon_id: 42 });
    expect(unmatchedMetaval([listed, unresolved, absent], new Set([11676]))).toEqual([
      unresolved,
      absent,
    ]);
  });
});
