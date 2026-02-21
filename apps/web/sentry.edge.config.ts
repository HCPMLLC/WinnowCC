import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "dev",
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});
