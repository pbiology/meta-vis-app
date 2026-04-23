export function axiosErrorDetail(e: unknown, fallback: string): string {
  if (typeof e === "object" && e !== null && "response" in e) {
    const response = (e as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export function axiosErrorStatus(e: unknown): number | null {
  if (typeof e === "object" && e !== null && "response" in e) {
    const status = (e as { response?: { status?: number } }).response?.status;
    if (typeof status === "number") return status;
  }
  return null;
}
