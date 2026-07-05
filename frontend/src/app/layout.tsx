import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aegis — Temporal Knowledge-Graph Digital Twin for Farmland",
  description:
    "Aegis builds a longitudinal soil-memory graph for your farmland. Ask plain-language questions and trace answers back to dated field notes, weather events, and chemical logs.",
  keywords: ["agronomy", "soil memory", "knowledge graph", "farmland digital twin", "cognee", "RAG", "agriculture AI"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#080d12" />
      </head>
      <body>{children}</body>
    </html>
  );
}
