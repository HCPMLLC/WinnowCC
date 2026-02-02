import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Winnow",
  description: "Match resumes to roles with confidence.",
  icons: {
    icon: "/Winnow Favico.ico",
  },
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
