import { http, HttpResponse } from "msw";

const API = "*/api/v1";

/**
 * One pipeline run of a case, as the API returns it.
 *
 * Kept minimal on purpose: no classifiers and no reports, so the default
 * payload stays as empty as the rest of this file. Tests that need a run with
 * data build their own (see CaseView.versions.test.tsx).
 */
function analysisFixture(caseId: string, version: number) {
  return {
    case_id: caseId,
    version,
    is_latest: true,
    review: { reviewed: false },
    classifiers: [],
    has_krona: false,
    has_multiqc: false,
    report_selections: {},
  };
}

/**
 * GET /cases/{id} and /cases/{id}/analyses/{v} — identity, the run being
 * viewed, and every run, nested rather than flattened.
 *
 * `analysis` is a real run rather than null: the backend 404s when a case has
 * no analysis, so a 200 always carries one. A fixture that omitted it crashed
 * the page on render.
 */
function caseDetailFixture(caseId: string, version: number) {
  return {
    case: { case_id: caseId, notes: [] },
    analysis: analysisFixture(caseId, version),
    analyses: [analysisFixture(caseId, version)],
  };
}

// Default handlers cover every endpoint the frontend touches with empty/permissive
// payloads. Individual tests override what they care about via server.use(...).
//
// Run-scoped resources are registered twice — bare and under
// /analyses/{version} — mirroring the backend, because setup.ts runs MSW with
// `onUnhandledRequest: "error"`: a path with no handler fails the request
// outright rather than falling through.
export const defaultHandlers = [
  // auth + users (identity owned by Keycloak; only /me/* lives on the API)
  http.get(`${API}/auth/me`, () => HttpResponse.json({ username: "tester", role: "admin" })),
  http.get(`${API}/users/me/stats`, () => HttpResponse.json({ reviews: 0 })),
  http.get(`${API}/users/me/preferences`, () =>
    HttpResponse.json({
      preferred_kingdoms: ["Viruses"],
      visible_analysis_types: ["shotgun", "amplicon"],
    })
  ),
  http.patch(`${API}/users/me/preferences`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      preferred_kingdoms: ["Viruses"],
      visible_analysis_types: ["shotgun", "amplicon"],
      ...body,
    });
  }),

  // cases
  http.get(`${API}/cases`, () =>
    HttpResponse.json({ items: [], total: 0, pages: 1, ticket_links_enabled: false })
  ),
  http.get(`${API}/cases/stats`, () => HttpResponse.json({ total: 0, pending: 0, reviewed: 0 })),
  http.get(`${API}/cases/pathogen_cases`, () => HttpResponse.json({ case_ids: [] })),
  http.get(`${API}/cases/:caseId`, ({ params }) =>
    HttpResponse.json(caseDetailFixture(String(params.caseId), 1))
  ),
  http.get(`${API}/cases/:caseId/analyses/:version`, ({ params }) =>
    HttpResponse.json(caseDetailFixture(String(params.caseId), Number(params.version)))
  ),
  http.delete(`${API}/cases/:caseId/analyses/:version`, () => HttpResponse.json({})),
  http.get(`${API}/cases/:caseId/samples`, () => HttpResponse.json([])),
  http.get(`${API}/cases/:caseId/analyses/:version/samples`, () => HttpResponse.json([])),
  http.get(`${API}/cases/:caseId/krona`, () => HttpResponse.html("<html>krona</html>")),
  http.get(`${API}/cases/:caseId/analyses/:version/krona`, () =>
    HttpResponse.html("<html>krona</html>")
  ),
  http.get(`${API}/cases/:caseId/multiqc`, () => HttpResponse.html("<html>multiqc</html>")),
  http.get(`${API}/cases/:caseId/analyses/:version/multiqc`, () =>
    HttpResponse.html("<html>multiqc</html>")
  ),
  http.patch(`${API}/cases/:caseId/review`, () => HttpResponse.json({})),
  http.patch(`${API}/cases/:caseId/analyses/:version/review`, () => HttpResponse.json({})),
  http.delete(`${API}/cases/:caseId/review`, () => HttpResponse.json({})),
  http.delete(`${API}/cases/:caseId/analyses/:version/review`, () => HttpResponse.json({})),
  http.patch(`${API}/cases/:caseId/report`, ({ params }) =>
    HttpResponse.json({ case_id: params.caseId, version: 1, selections: {} })
  ),
  http.patch(`${API}/cases/:caseId/analyses/:version/report`, ({ params }) =>
    HttpResponse.json({
      case_id: params.caseId,
      version: Number(params.version),
      selections: {},
    })
  ),
  http.post(`${API}/cases/:caseId/analyses/:version/report/carry-forward`, ({ params }) =>
    HttpResponse.json({
      case_id: params.caseId,
      version: Number(params.version),
      from_version: Number(params.version) - 1,
      applied: {},
      dropped: [],
    })
  ),
  http.delete(`${API}/cases/:caseId`, () => HttpResponse.json({})),
  http.post(`${API}/cases/:caseId/notes`, () => HttpResponse.json({})),
  http.delete(`${API}/cases/:caseId/notes/:noteIndex`, () => HttpResponse.json({})),

  // samples
  http.get(`${API}/samples`, () => HttpResponse.json({ items: [], total: 0, pages: 1, page: 1 })),
  http.get(`${API}/samples/:sampleId/profile`, () => HttpResponse.json({ profiles: [] })),
  http.get(`${API}/samples/:sampleId/ntc_profiles`, () =>
    HttpResponse.json({ profiles: [], contaminant_config: null })
  ),
  http.get(`${API}/samples/:sampleId`, ({ params }) =>
    HttpResponse.json({ sample_id: params.sampleId, sample_type: "sample" })
  ),

  // subjects
  http.get(`${API}/subjects`, () => HttpResponse.json({ total: 0, page: 1, pages: 1, items: [] })),
  http.get(`${API}/subjects/:subjectId/cases`, () => HttpResponse.json([])),
  http.get(`${API}/subjects/:subjectId`, ({ params }) =>
    HttpResponse.json({ subject_id: params.subjectId })
  ),

  // metaval
  http.get(`${API}/metaval/sample/:sampleId`, () => HttpResponse.json([])),
  http.get(`${API}/metaval/:metavalId`, ({ params }) =>
    HttpResponse.json({ _id: params.metavalId, sample_id: "s1" })
  ),

  // taxa
  http.get(`${API}/taxa/:taxonId`, ({ params }) =>
    HttpResponse.json({ taxon_id: Number(params.taxonId), name: "Test taxon" })
  ),
  http.get(`${API}/taxa/:taxonId/occurrences`, () => HttpResponse.json({})),
  http.patch(`${API}/taxa/:taxonId/clinical_notes`, () => HttpResponse.json({})),
  http.get(`${API}/taxa/:taxonId/external_links`, () => HttpResponse.json({})),
  http.get(`${API}/taxa/:taxonId/literature`, () => HttpResponse.json({})),
  http.get(`${API}/taxa/:taxonId/bvbrc/genomes`, () => HttpResponse.json({})),
  http.get(`${API}/taxa/:taxonId/bvbrc/specialty_genes`, () => HttpResponse.json({})),

  // alerts
  http.get(`${API}/alerts/outbreaks`, () => HttpResponse.json({ window_days: 14, outbreaks: [] })),
  http.get(`${API}/alerts/ignorelist`, () => HttpResponse.json([])),
  http.post(`${API}/alerts/ignorelist`, () => HttpResponse.json({})),
  http.delete(`${API}/alerts/ignorelist/:taxonId`, () => HttpResponse.json({})),
  http.patch(`${API}/alerts/ignorelist/:taxonId`, () => HttpResponse.json({})),
  http.get(`${API}/alerts/pathogens`, () => HttpResponse.json([])),
  http.post(`${API}/alerts/pathogens`, () => HttpResponse.json({})),
  http.delete(`${API}/alerts/pathogens/:taxonId`, () => HttpResponse.json({})),

  // ntc
  http.get(`${API}/ntc/trends`, () =>
    HttpResponse.json({
      total_ntcs: 0,
      min_case_count: 0,
      kingdom_breakdown: [],
      read_counts: [],
      recurring_taxa: [],
    })
  ),
  http.get(`${API}/ntc/ignorelist`, () => HttpResponse.json([])),
  http.post(`${API}/ntc/ignorelist`, () => HttpResponse.json({})),
  http.patch(`${API}/ntc/ignorelist/:taxonId`, () => HttpResponse.json({})),
  http.delete(`${API}/ntc/ignorelist/:taxonId`, () => HttpResponse.json({})),
  http.get(`${API}/ntc/contaminants`, () => HttpResponse.json([])),
  http.post(`${API}/ntc/contaminants`, () => HttpResponse.json({})),
  http.patch(`${API}/ntc/contaminants/:taxonId`, () => HttpResponse.json({})),
  http.delete(`${API}/ntc/contaminants/:taxonId`, () => HttpResponse.json({})),
  http.get(`${API}/ntc/contaminant-alerts`, () =>
    HttpResponse.json({ contaminant_case_ids: [], alerts: [] })
  ),
];
