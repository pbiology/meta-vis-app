/**
 * Display labels for analysis metadata.
 *
 * Shared so the Cases list, the per-case rows and the Subject detail page all
 * spell these the same way — they previously each had their own copy.
 */

/** "shotgun" → "Shotgun". Unknown or missing values render as an em dash. */
export function analysisLabel(type: unknown): string {
  if (type === "shotgun") return "Shotgun";
  if (type === "amplicon") return "Amplicon";
  return "—";
}

/** "illumina" → "Illumina". Unknown or missing values render as an em dash. */
export function platformLabel(platform?: string | null): string {
  if (!platform) return "—";
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}
