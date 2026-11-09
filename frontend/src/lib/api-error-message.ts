// Only display documented human-readable fields, never stringify a payload
// (validation entries may contain the submitted input or other private data).
export function apiErrorMessage(value: unknown, fallback: string): string {
  const text = (v: unknown) => typeof v === "string" ? v.trim().slice(0, 500) : "";
  if (typeof value === "string") return text(value) || fallback;
  if (!value || typeof value !== "object") return fallback;
  const detail = "detail" in value ? value.detail : value;
  if (typeof detail === "string") return text(detail) || fallback;
  if (Array.isArray(detail)) {
    const messages = detail.slice(0, 3).map((entry: unknown) =>
      entry && typeof entry === "object" && "msg" in entry ? text(entry.msg) : "",
    ).filter(Boolean);
    return messages.join("; ").slice(0, 500) || fallback;
  }
  return detail && typeof detail === "object" && "message" in detail
    ? text(detail.message) || fallback : fallback;
}
