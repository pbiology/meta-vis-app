export type AnalysisType = "shotgun" | "amplicon";

export const ALL_ANALYSIS_TYPES: AnalysisType[] = ["shotgun", "amplicon"];

// For endpoints that take a single analysis_type value ("shotgun" | "amplicon" | null).
// urlOverride: the explicit user choice from the URL; wins when not "all".
// visible: the user's preference (visible_analysis_types).
// Returns the value to send as ?analysis_type=... , or null to omit the param.
export function singleAnalysisFilter(
  visible: string[] | null | undefined,
  urlOverride: string = "all"
): AnalysisType | null {
  if (urlOverride === "shotgun" || urlOverride === "amplicon") {
    return urlOverride;
  }
  const v = visible ?? ALL_ANALYSIS_TYPES;
  if (v.length === 1) return v[0] as AnalysisType;
  return null;
}

// For endpoints that take a list (analysis_types[]). Returns null when both
// types are visible (omit the param → hits warm cache on backend).
export function multiAnalysisFilter(visible: string[] | null | undefined): string[] | null {
  const v = visible ?? ALL_ANALYSIS_TYPES;
  if (v.length === 0 || v.length === ALL_ANALYSIS_TYPES.length) return null;
  return v;
}
