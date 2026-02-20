"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Only load Sentry when DSN is configured (production).
    // In dev the DSN is empty, so skip the import entirely — this avoids
    // pulling in @sentry/node → Prisma → OpenTelemetry on every HMR cycle.
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (dsn) {
      import("@sentry/nextjs").then((Sentry) => {
        Sentry.captureException(error);
      });
    } else {
      console.error("Global error:", error);
    }
  }, [error]);

  return (
    <html>
      <body>
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2>Something went wrong</h2>
          <p>We&apos;ve been notified and are looking into it.</p>
          <button
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
