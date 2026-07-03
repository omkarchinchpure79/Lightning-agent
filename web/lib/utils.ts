import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
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
