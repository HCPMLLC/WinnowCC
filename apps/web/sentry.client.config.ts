import * as Sentry from "@sentry/nextjs";

// Only initialize Sentry if user has accepted analytics cookies (GDPR).
// On first visit consent is "pending" so Sentry stays off until accepted.
const consent =
  typeof window !== "undefined"
    ? localStorage.getItem("winnow_cookie_consent")
    : null;

if (consent === "accepted") {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "dev",

    // Performance monitoring
    tracesSampleRate: 0.1,

    // Session replay (optional — captures user sessions on error)
    replaysSessionSampleRate: 0, // Don't record normal sessions
    replaysOnErrorSampleRate: 0.1, // Record 10% of sessions with errors

    // Don't send PII
    sendDefaultPii: false,
  });
}
