import "./globals.css";
import type { Metadata } from "next";
import CookieConsent from "./components/CookieConsent";
import Navbar from "./components/Navbar";
import AuthenticatedSieve from "./components/sieve/AuthenticatedSieve";
import CandidateDisclaimer from "./components/CandidateDisclaimer";
import QueryProvider from "./providers/QueryProvider";

export const metadata: Metadata = {
  title: "Winnow Career Concierge",
  description: "Know the odds before you apply. AI-powered job matching with Interview Probability Scores for candidates, employers, and recruiters.",
  metadataBase: new URL("https://winnowcc.ai"),
  icons: {
    icon: "/logo.png",
  },
  openGraph: {
    title: "Winnow Career Concierge",
    description: "Know the odds before you apply.",
    url: "https://winnowcc.ai",
    siteName: "Winnow Career Concierge",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Winnow Career Concierge – Know the odds before you apply.",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Winnow Career Concierge",
    description: "Know the odds before you apply.",
    images: ["/og-image.png"],
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
