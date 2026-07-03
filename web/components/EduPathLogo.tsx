"use client";

/**
 * EduPathMark — the bezier/anchor logo mark, inline so it inherits currentColor
 * and never depends on a scraped PNG. Green filled dot = the start (a student's
 * percentile); blue ring = the destination (a seat). The curve is the "path".
 *
 * Use <EduPathLogo /> for the full lockup (mark + serif wordmark).
 */
export function EduPathMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9 33 C 9 16, 16 10, 31 10"
        stroke="var(--color-ep-primary)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <circle cx="9" cy="33" r="4.4" fill="var(--color-ep-green)" />
      <circle
        cx="31"
        cy="10"
        r="4.2"
        fill="var(--ep-bg)"
        stroke="var(--color-ep-primary)"
        strokeWidth="3"
      />
    </svg>
  );
}

export function EduPathLogo({ size = 28 }: { size?: number }) {
  return (
    <span className="flex items-center gap-2.5">
      <EduPathMark size={size} />
      <span
        className="font-display leading-none"
        style={{ fontSize: size * 0.8, color: "var(--ep-text)" }}
      >
        EduPath
      </span>
    </span>
  );
}
