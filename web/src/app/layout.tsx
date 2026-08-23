import type { Metadata } from "next";
import "./globals.css";
import { Navigation } from "@/components/Navigation";

export const metadata: Metadata = {
  title: "ATLAS — Autonomous Trading & Learning Analysis System",
  description: "Quantitative Trading & Strategy Validation Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-bg text-text-1 antialiased min-h-screen flex">
        <Navigation />
        <main className="flex-1 min-w-0 p-8 overflow-y-auto max-h-screen">
          <div className="max-w-7xl mx-auto space-y-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
