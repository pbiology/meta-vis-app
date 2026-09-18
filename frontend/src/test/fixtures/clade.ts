import type { CladeCell, CladeNode, CladeResponse } from "../../api/types";

export function cell(direct: number, clade: number, total: number | null = 1_000_000): CladeCell {
  return {
    direct,
    clade,
    direct_rpm: total ? (direct / total) * 1_000_000 : null,
    clade_rpm: total ? (clade / total) * 1_000_000 : null,
  };
}

function node(
  taxon_id: number,
  name: string,
  rank: string | null,
  cells: CladeNode["cells"],
  children: CladeNode[] = [],
  extra: Partial<CladeNode> = {}
): CladeNode {
  const is_connector = Object.values(cells).every((c) => c.direct === 0);
  return { taxon_id, name, rank, cells, is_connector, merged_from: [], children, ...extra };
}

/**
 * Escherichia opened from the O157:H7 serotype. The sample carries O157:H7;
 * the NTC carries reads on the genus itself, K-12 (partly via merged taxid 12)
 * and MG1655 below it. E. coli has no direct reads, so it is a connector.
 * MG1655 sits at depth 3, below the default two open levels and off the
 * clicked taxon's path, so it starts hidden. NTC2 has no kraken2 profile.
 */
export function escherichiaClade(): CladeResponse {
  const mg1655 = node(511145, "Escherichia coli str. K-12 substr. MG1655", "strain", {
    S1: cell(0, 0),
    NTC1: cell(2, 2),
  });
  const k12 = node(
    83333,
    "Escherichia coli K-12",
    "strain",
    { S1: cell(0, 0), NTC1: cell(7, 9) },
    [mg1655],
    { merged_from: [12] }
  );
  const o157 = node(83334, "Escherichia coli O157:H7", "serotype", {
    S1: cell(100, 100),
    NTC1: cell(0, 0),
  });
  const eColi = node(562, "Escherichia coli", "species", { S1: cell(0, 100), NTC1: cell(0, 9) }, [
    o157,
    k12,
  ]);
  return {
    classifier: "kraken2",
    unit: "reads",
    clicked: { taxon_id: 83334, name: "Escherichia coli O157:H7", rank: "serotype" },
    anchor: { taxon_id: 561, name: "Escherichia", rank: "genus" },
    columns: [
      { sample_id: "S1", sample_type: "sample", has_profile: true, classifier_total: 1_000_000 },
      {
        sample_id: "NTC1",
        sample_type: "negative_ctrl",
        has_profile: true,
        classifier_total: 1_000_000,
      },
      {
        sample_id: "NTC2",
        sample_type: "negative_ctrl",
        has_profile: false,
        classifier_total: null,
      },
    ],
    root: node(561, "Escherichia", "genus", { S1: cell(0, 100), NTC1: cell(3, 12) }, [eColi]),
    unplaced: [],
  };
}

/**
 * The Streptomyces shape: one genus with many sibling species, nearly all of
 * them only in the control. `ntcOnly` species are ordered by descending reads
 * as the backend sorts them; species 9001 has two reads in the sample and is
 * deliberately the weakest, so folding rules can be checked against it.
 */
export function wideClade(ntcOnly = 25): CladeResponse {
  const controlSpecies = Array.from({ length: ntcOnly }, (_, i) =>
    node(8000 + i, `Streptomyces sp. C${i}`, "species", {
      S1: cell(0, 0),
      NTC1: cell((ntcOnly - i) * 10, (ntcOnly - i) * 10),
    })
  );
  const weakInSample = node(9001, "Streptomyces xinghaiensis", "species", {
    S1: cell(2, 2),
    NTC1: cell(0, 0),
  });
  return {
    classifier: "kraken2",
    unit: "reads",
    clicked: { taxon_id: 9001, name: "Streptomyces xinghaiensis", rank: "species" },
    anchor: { taxon_id: 1883, name: "Streptomyces", rank: "genus" },
    columns: [
      { sample_id: "S1", sample_type: "sample", has_profile: true, classifier_total: 1_000_000 },
      {
        sample_id: "NTC1",
        sample_type: "negative_ctrl",
        has_profile: true,
        classifier_total: 1_000_000,
      },
    ],
    root: node(1883, "Streptomyces", "genus", { S1: cell(0, 2), NTC1: cell(0, 3380) }, [
      weakInSample,
      ...controlSpecies,
    ]),
    unplaced: [],
  };
}
