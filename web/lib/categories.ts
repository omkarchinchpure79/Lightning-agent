/**
 * Category grouping for the branch-forecast tree.
 *
 * MHT-CET CAP publishes ~100 distinct category codes per branch — every
 * combination of audience (General / Ladies / Defence / PwD), base reservation
 * (Open, OBC, SC, ST, VJ, NT1-3, SEBC) and seat-type (H = Home university,
 * O = Other than home, S = State level), plus a few standalone pools (EWS,
 * TFWS, Orphan). Showing all of them flat overwhelms the counsellor.
 *
 * So the forecast groups them into a two-level tree: a handful of top-level
 * FAMILIES (the base reservation category, or Defence/PwD/standalone as their
 * own family), with the individual codes as expandable child VARIANTS. Only
 * the families a given branch actually has data for are shown — nothing is
 * invented. This is presentation only; the underlying per-code cutoffs are
 * unchanged and still reachable by expanding.
 */

export interface CategoryParts {
  raw: string;
  familyKey: string; // grouping key: OPEN, OBC, SC, ST, VJ, NT1, NT2, NT3, SEBC, EWS, TFWS, DEF, PWD, ORPHAN, OTHER
  familyLabel: string;
  familyOrder: number;
  primary: boolean; // shown at first impression (rest behind "More categories")
  audience: "General" | "Ladies" | "Defence" | "PwD" | "Open";
  seat: "H" | "O" | "S" | null;
  variantLabel: string; // human label for the expandable child row
  variantOrder: number;
}

interface FamilyMeta {
  label: string;
  order: number;
  primary: boolean;
}

// Base reservation categories (after stripping audience prefix + seat suffix).
const BASE_FAMILY: Record<string, FamilyMeta> = {
  OPEN: { label: "Open / General", order: 1, primary: true },
  OBC: { label: "OBC", order: 2, primary: true },
  SC: { label: "SC", order: 3, primary: true },
  ST: { label: "ST", order: 4, primary: true },
  EWS: { label: "EWS", order: 5, primary: true },
  VJ: { label: "VJ / DT (VJ-A)", order: 6, primary: false },
  NT1: { label: "NT-B (NT-1)", order: 7, primary: false },
  NT2: { label: "NT-C (NT-2)", order: 8, primary: false },
  NT3: { label: "NT-D (NT-3)", order: 9, primary: false },
  SEBC: { label: "SEBC", order: 10, primary: false },
  TFWS: { label: "TFWS", order: 11, primary: false },
  DEF: { label: "Defence", order: 12, primary: false },
  PWD: { label: "PwD", order: 13, primary: false },
  ORPHAN: { label: "Orphan", order: 14, primary: false },
  OTHER: { label: "Other", order: 99, primary: false },
};

const SEAT_LABEL: Record<string, string> = {
  H: "Home university",
  O: "Other than home",
  S: "State level",
};
const SEAT_ORDER: Record<string, number> = { H: 0, S: 1, O: 2 };

/** Split a category code into family + variant metadata. */
export function parseCategory(raw: string): CategoryParts {
  const code = (raw ?? "").toUpperCase().trim();

  const mk = (
    familyKey: string,
    audience: CategoryParts["audience"],
    seat: CategoryParts["seat"],
    variantLabel: string,
    variantOrder: number,
  ): CategoryParts => {
    const fam = BASE_FAMILY[familyKey] ?? BASE_FAMILY.OTHER;
    return {
      raw,
      familyKey,
      familyLabel: fam.label,
      familyOrder: fam.order,
      primary: fam.primary,
      audience,
      seat,
      variantLabel,
      variantOrder,
    };
  };

  // Standalone pools — one row each, their own family.
  if (code === "EWS") return mk("EWS", "Open", null, "EWS", 0);
  if (code === "TFWS") return mk("TFWS", "Open", null, "TFWS", 0);
  if (code === "ORPHAN") return mk("ORPHAN", "Open", null, "Orphan", 0);

  // Audience prefix (longest match first so DEFR beats DEF, PWDR beats PWD).
  let audience: CategoryParts["audience"];
  let reserved = false;
  let rest = code;
  if (code.startsWith("DEFR")) { audience = "Defence"; reserved = true; rest = code.slice(4); }
  else if (code.startsWith("DEF")) { audience = "Defence"; rest = code.slice(3); }
  else if (code.startsWith("PWDR")) { audience = "PwD"; reserved = true; rest = code.slice(4); }
  else if (code.startsWith("PWD")) { audience = "PwD"; rest = code.slice(3); }
  else if (code.startsWith("L")) { audience = "Ladies"; rest = code.slice(1); }
  else if (code.startsWith("G")) { audience = "General"; rest = code.slice(1); }
  else { audience = "Open"; rest = code; }

  // Seat suffix (H/O/S) — never collides with any base ending.
  let seat: CategoryParts["seat"] = null;
  if (rest.length > 1 && (rest.endsWith("H") || rest.endsWith("O") || rest.endsWith("S"))) {
    seat = rest.slice(-1) as "H" | "O" | "S";
    rest = rest.slice(0, -1);
  }

  const base = rest || "OTHER";
  const seatText = seat ? SEAT_LABEL[seat] : null;
  const seatOrder = seat ? SEAT_ORDER[seat] : 3;

  // Defence / PwD are their own family (they cut across base categories);
  // the base + seat become the variant label. Everyone else is grouped by base.
  if (audience === "Defence" || audience === "PwD") {
    const famKey = audience === "Defence" ? "DEF" : "PWD";
    const baseLbl = BASE_FAMILY[base]?.label.split(" / ")[0] ?? base;
    const parts = [baseLbl, seatText, reserved ? "Reserved" : null].filter(Boolean);
    return mk(famKey, audience, seat, parts.join(" · "), seatOrder + (reserved ? 100 : 0));
  }

  // General / Ladies grouped under the base family; audience + seat is the variant.
  const audienceOrder = audience === "General" ? 0 : audience === "Ladies" ? 1000 : 2000;
  const variantLabel = [audience, seatText].filter(Boolean).join(" · ");
  return mk(base, audience, seat, variantLabel, audienceOrder + seatOrder);
}
