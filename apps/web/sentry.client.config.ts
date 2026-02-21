import * as Sentry from "@sentry/nextjs";

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
