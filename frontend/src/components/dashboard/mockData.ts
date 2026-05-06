// Mocked dashboard widget data for v1 of the dashboard redesign.
// Each export below stands in for a backend endpoint that does not exist yet.
// When the endpoint lands, swap the import — the component contract is stable.

// TODO(backend): GET /api/v1/cases/volume?days=14 — daily counts split by routine vs pathogen.
export interface VolumePoint {
  day: string;
  total: number;
  pathogen: number;
}

const today = new Date();
function daysAgoISO(n: number): string {
  const d = new Date(today);
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export const VOLUME_14D: VolumePoint[] = Array.from({ length: 14 }, (_, i) => {
  const idx = i;
  const total = 4 + Math.round(Math.sin(idx / 2.1) * 3 + ((idx * 7) % 5));
  const pathogen = Math.max(0, Math.round(Math.sin(idx / 3) * 1.2 + ((idx * 3) % 2)));
  return { day: daysAgoISO(13 - idx), total, pathogen };
});

// TODO(backend): GET /api/v1/alerts/top-pathogens?days=14 — distinct from outbreak alerts.
export interface PathogenTrend {
  name: string;
  count: number;
  last: string;
}

export const TOP_PATHOGENS_14D: PathogenTrend[] = [
  { name: "M. tuberculosis", count: 6, last: "Today" },
  { name: "Influenza A", count: 4, last: "Yesterday" },
  { name: "S. aureus", count: 3, last: "2d ago" },
  { name: "E. coli STEC", count: 2, last: "3d ago" },
];

// TODO(backend): GET /api/v1/users/leaderboard — admin-visible reviewer activity.
export interface ReviewerActivity {
  name: string;
  reviewed: number;
  pending: number;
}

export const REVIEWER_LEADERBOARD: ReviewerActivity[] = [
  { name: "ebystedt", reviewed: 24, pending: 3 },
  { name: "mlarsson", reviewed: 19, pending: 2 },
  { name: "lindgren", reviewed: 14, pending: 5 },
  { name: "aperson", reviewed: 8, pending: 1 },
];

// TODO(backend): aggregate from cases collection — average days between order_date
// and review.reviewed_at for cases reviewed in the last 14 days.
export const MOCK_AVG_TURNAROUND = "2.3d";

// TODO(backend): aggregate from QC — share of samples meeting Q30 threshold.
export const MOCK_PASS_RATE = "97%";
