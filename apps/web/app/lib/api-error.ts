/**
 * Extract a human-readable error message from a FastAPI error response.
 *
 * FastAPI returns `detail` as a string for HTTPException (400/403/404)
 * but as an array of objects for Pydantic validation errors (422).
 * Passing the array straight to `new Error()` or into JSX produces
 * "[object Object]".  This helper normalises both shapes to a string.
 */
export function parseApiError(
  data: { detail?: unknown },
  fallback = "Something went wrong",
): string {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const msgs = d
      .map((e: { msg?: string }) =>
        (e.msg || String(e)).replace(/^Value error, /i, ""),
      )
      .filter(Boolean);
    if (msgs.length) return msgs.join(". ");
  }
  return fallback;
}
