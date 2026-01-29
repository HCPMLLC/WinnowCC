import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ResumeMatch",
  description: "Match resumes to roles with confidence.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}