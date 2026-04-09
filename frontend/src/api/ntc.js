import client from "./client";

export async function getNtcTrends({ material, windowDays = 90, minReads = 3, minCasePct = 0.1 }) {
  const res = await client.get("/ntc/trends", {
    params: {
      material,
      window_days: windowDays,
      min_reads: minReads,
      min_case_pct: minCasePct,
    },
  });
  return res.data;
}
