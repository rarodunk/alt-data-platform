import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Alt Data Platform",
  description: "Alternative data forecasting for DUOL, LMND, NU, TMDX",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
