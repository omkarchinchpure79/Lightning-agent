import type { Metadata } from "next";
import {
  DM_Serif_Display,
  DM_Sans,
  DM_Mono,
} from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// ── "Hearth" type system ─────────────────────────────────────────
// DM Sans          → body / UI
// DM Serif Display → serif accents + display headings (college names, h1s, hero)
// DM Mono          → numbers, codes, labels
// Var names kept as before ("--font-public-sans" etc.) so globals.css / no
// other file needs to change — only the font family swaps.
const publicSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-public-sans",
  display: "swap",
});
const newsreader = DM_Serif_Display({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
});
const instrumentSerif = DM_Serif_Display({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});
const plexMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
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
