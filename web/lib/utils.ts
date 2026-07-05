import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Format a percentile for display without the rounding artifact that made a
// sub-100 prediction (e.g. VJTI CSE's 99.9523) render as "100.0" in the
// headline while the 2-decimal chart still showed 99.95. A value strictly
// below 100 must never display as 100 — cap it just under 100 so the shown
// number never overstates a percentile the model didn't actually reach.
// Everything else rounds normally, so this only touches the 99.95–99.999 edge.
export function fmtPercentile(v: number | null | undefined, dp = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  const rounded = Number(v.toFixed(dp));
  if (v < 100 && rounded >= 100) {
    return (100 - Math.pow(10, -dp)).toFixed(dp); // 99.9 (dp=1) / 99 (dp=0)
  }
  return rounded.toFixed(dp);
}

// Transform Google Maps CDN image URLs to the requested size.
// URLs look like: ...=w1080-h720-k-no  (size prefix, optional flags like -k-no)
// We replace only the w/h portion and preserve any trailing flags.
//
// No-op for anything that isn't a googleusercontent.com URL (e.g. our own
// /static/images/... locally-downloaded photos, or Wikipedia/college-site
// URLs) — appending a Google size suffix to those corrupts the URL into a
// 404 (this exact bug shipped once already; don't reintroduce it).
export function googleImageUrl(
  url: string,
  size: "hero" | "gallery" | "thumb"
): string {
  if (!url.includes("googleusercontent.com")) {
    return url;
  }
  const sizeStr = { hero: "w1200-h900", gallery: "w800-h600", thumb: "w400-h300" }[size];
  // Match =wNNN-hNNN and capture any trailing flags (e.g. -k-no)
  const match = url.match(/=(w\d+-h\d+)(.*)/);
  if (match) {
    const flags = match[2] ?? "";
    return url.replace(/=w\d+-h\d+.*/, `=${sizeStr}${flags}`);
  }
  return `${url}=${sizeStr}`;
}
