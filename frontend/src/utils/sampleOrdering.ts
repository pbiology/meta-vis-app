// Canonical case-level sample ordering used by the report. DNA before RNA;
// other sample types fall through to insertion order (which the API returns
// in ingestion order). Adding a third type is a one-line edit.
const SAMPLE_TYPE_ORDER = ["DNA", "RNA"] as const;

function rank(sampleType: string | undefined): number {
  if (!sampleType) return SAMPLE_TYPE_ORDER.length;
  const upper = sampleType.toUpperCase();
  const i = SAMPLE_TYPE_ORDER.indexOf(upper as (typeof SAMPLE_TYPE_ORDER)[number]);
  return i === -1 ? SAMPLE_TYPE_ORDER.length : i;
}

export function compareBySampleType<T>(a: T, b: T): number {
  const aType = (a as { sample_type?: unknown }).sample_type;
  const bType = (b as { sample_type?: unknown }).sample_type;
  return (
    rank(typeof aType === "string" ? aType : undefined) -
    rank(typeof bType === "string" ? bType : undefined)
  );
}
