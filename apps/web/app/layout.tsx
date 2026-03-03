import "./globals.css";
import type { Metadata } from "next";
import CookieConsent from "./components/CookieConsent";
import Navbar from "./components/Navbar";
import AuthenticatedSieve from "./components/sieve/AuthenticatedSieve";
import CandidateDisclaimer from "./components/CandidateDisclaimer";
import QueryProvider from "./providers/QueryProvider";

export const metadata: Metadata = {
  title: "Winnow Career Concierge",
  description: "Match resumes to roles with confidence.",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <head>
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- App Router: layout.tsx is the equivalent of _document.js */}
        <link
          href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <QueryProvider>
          <Navbar />
          {children}
          <CandidateDisclaimer />
          <CookieConsent />
          <AuthenticatedSieve />
        </QueryProvider>
      </body>
    </html>
  );
}
