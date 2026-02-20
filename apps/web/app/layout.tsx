import "./globals.css";
import type { Metadata } from "next";
import Navbar from "./components/Navbar";
import AuthenticatedSieve from "./components/sieve/AuthenticatedSieve";

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
      <body>
        <Navbar />
        {children}
        <AuthenticatedSieve />
      </body>
    </html>
  );
}
