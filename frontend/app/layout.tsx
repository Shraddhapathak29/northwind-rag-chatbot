import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Northwind Gadgets — Support Assistant",
  description: "Dual-mode agentic RAG chatbot (vector RAG + text-to-SQL)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
