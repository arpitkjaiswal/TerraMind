import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TerraMind — Field Intelligence & Evidence Explorer",
  description:
    "Explore agricultural records, interactive knowledge graphs, and evidence-linked search. Try the private browser sandbox without creating an account.",
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
