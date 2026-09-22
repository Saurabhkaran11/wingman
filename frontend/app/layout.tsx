import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "./globals.css";

// next/font downloads these at build time and self-hosts them, so a running
// Wingman never calls out to Google and works offline.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  variable: "--font-display",
  display: "swap",
});

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Wingman",
  description: "The agent that briefs you before every meeting.",
};

export const viewport: Viewport = {
  themeColor: "#e9ecf3",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <head>
        <link
          rel="icon"
          href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%234c6fff' stroke-width='2'><circle cx='6' cy='7' r='2.4'/><circle cx='18' cy='6' r='2.4'/><circle cx='12' cy='17' r='2.4'/><path d='M7.7 8.6l3 6.2M16.6 8.1l-3.3 6.9M8.3 6.6h7.3'/></svg>"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
