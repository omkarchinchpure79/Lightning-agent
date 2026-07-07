import type { Metadata } from "next";
import {
  Sora,
  Manrope,
  IBM_Plex_Mono,
} from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// ── Type system, built around the real EduPath mark (blue path / green dot) ──
// Manrope    → body / UI / entity names (serif role folds into this — see globals.css)
// Sora       → display headings (its circular counters echo the logo's ring)
// IBM Plex Mono → percentiles, codes, ranks — tabular figures for data alignment
// Var names kept as before ("--font-public-sans" etc.) so globals.css / no
// other file needs to change — only the font family swaps.
const publicSans = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-public-sans",
  display: "swap",
});
const instrumentSerif = Sora({
  subsets: ["latin"],
  weight: ["600", "700"],
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
  const fontVars = `${publicSans.variable} ${instrumentSerif.variable} ${plexMono.variable}`;
  return (
    <html lang="en" suppressHydrationWarning className={fontVars}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
