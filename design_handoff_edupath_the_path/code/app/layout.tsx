import type { Metadata } from "next";
import {
  Instrument_Serif,
  Newsreader,
  Public_Sans,
  IBM_Plex_Mono,
} from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// ── "The Path" type system ──────────────────────────────────────
// Public Sans  → body / UI
// Newsreader   → serif accents (college names, descriptions)
// Instrument   → display headings (h1s, hero)
// IBM Plex Mono → numbers, codes, labels
const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-public-sans",
  display: "swap",
});
const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
});
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "EduPath — MHT-CET Counsellor",
  description: "College seat allotment prediction for MHT-CET CAP counsellors",
  icons: {
    icon: [
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fontVars = `${publicSans.variable} ${newsreader.variable} ${instrumentSerif.variable} ${plexMono.variable}`;
  return (
    <html lang="en" suppressHydrationWarning className={fontVars}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
