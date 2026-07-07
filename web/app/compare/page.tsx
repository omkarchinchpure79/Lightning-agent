"use client";

import { Suspense, useEffect, useMemo, useState, useRef } from "react";
import { useQueries, type UseQueryResult } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  X,
  Plus,
  Search,
  AlertTriangle,
  GitCompareArrows,
  Sparkles,
  GraduationCap,
  Landmark,
  BarChart3,
  Wallet,
  MapPin,
  TrendingUp,
  Star,
} from "lucide-react";

import {
  getCollegeProfile,
  searchColleges,
  type CollegeProfile,
  type CollegeFeeEntry,
} from "@/lib/api";
import { cn, fmtPercentile, googleImageUrl } from "@/lib/utils";
import { useCompare, MAX_COMPARE, MIN_COMPARE, type CompareCollege } from "@/lib/useCompare";
import { NavHeader } from "@/components/NavHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// ── Derived facts (computed client-side from data the profile already returns) ─

interface DerivedFacts {
  toughestBranch: { name: string; close2025: number | null; pred2026: number | null } | null;
  branchCount: number;
}

function deriveFacts(p: CollegeProfile): DerivedFacts {
  if (!p.cutoff_trends.length) return { toughestBranch: null, branchCount: 0 };
  let best = p.cutoff_trends[0];
  for (const row of p.cutoff_trends) {
    const a = row.close_2025 ?? row.pred_2026 ?? -1;
    const b = best.close_2025 ?? best.pred_2026 ?? -1;
    if (a > b) best = row;
  }
  return {
    toughestBranch: { name: best.branch_name, close2025: best.close_2025, pred2026: best.pred_2026 },
    branchCount: p.cutoff_trends.length,
  };
}

function institutionLabel(type: string | null): string {
  if (!type) return "—";
  const t = type.toLowerCase();
  if (t.includes("gov")) return "Government";
  if (t.includes("aided")) return "Government-Aided";
  if (t.includes("pvt") || t.includes("priv")) return "Private";
  return type;
}

function fmtFee(fee: CollegeFeeEntry): string {
  if (!fee.available) return "N/A";
  return `₹${(fee.total_annual ?? 0).toLocaleString("en-IN")}/yr`;
}

function yesNo(v: number | null): "Yes" | "No" | "—" {
  return v === 1 ? "Yes" : v === 0 ? "No" : "—";
}

// ── Section / row config — one row per section covers a whole profile field,
// so "every section" of the college profile is represented here. ─────────────

interface Row {
  label: string;
  get: (p: CollegeProfile, facts: DerivedFacts) => string;
}
interface SectionCfg {
  key: string;
  title: string;
  icon: React.ReactNode;
  rows: Row[];
}

const FEE_CATS = ["GOPEN", "GOBC", "GSC", "TFWS"] as const;

const SECTIONS: SectionCfg[] = [
  {
    key: "overview",
    title: "Overview",
    icon: <Sparkles className="h-4 w-4" />,
    rows: [
      { label: "Quality score", get: (p) => (p.score.overall != null ? `${p.score.overall}/100` : "—") },
      { label: "Institution type", get: (p) => institutionLabel(p.identity.institution_type) },
      { label: "Established", get: (p) => p.identity.year_established?.toString() ?? "—" },
      { label: "Autonomous", get: (p) => yesNo(p.identity.is_autonomous) },
      { label: "Affiliated university", get: (p) => p.location.affiliated_university ?? "—" },
      { label: "District", get: (p) => p.location.district ?? "—" },
    ],
  },
  {
    key: "accreditation",
    title: "Accreditation",
    icon: <GraduationCap className="h-4 w-4" />,
    rows: [
      { label: "NAAC grade", get: (p) => p.accreditation.naac_grade ?? "—" },
      { label: "NIRF rank", get: (p) => (p.accreditation.nirf_rank != null ? `#${p.accreditation.nirf_rank}` : "—") },
      { label: "NBA-accredited branches", get: (p) => p.accreditation.nba_branches ?? "—" },
    ],
  },
  {
    key: "admissions",
    title: "Admissions & Cutoffs",
    icon: <TrendingUp className="h-4 w-4" />,
    rows: [
      { label: "Toughest branch", get: (_p, f) => f.toughestBranch?.name ?? "—" },
      {
        label: "2025 closing percentile",
        get: (_p, f) => (f.toughestBranch?.close2025 != null ? fmtPercentile(f.toughestBranch.close2025, 2) : "—"),
      },
      {
        label: "2026 predicted close",
        get: (_p, f) => (f.toughestBranch?.pred2026 != null ? fmtPercentile(f.toughestBranch.pred2026) : "—"),
      },
      { label: "Branches offered", get: (_p, f) => (f.branchCount ? String(f.branchCount) : "—") },
    ],
  },
  {
    key: "placements",
    title: "Placements",
    icon: <BarChart3 className="h-4 w-4" />,
    rows: [
      { label: "Placement rate", get: (p) => (p.placements.placement_pct != null ? `${p.placements.placement_pct}%` : "—") },
      { label: "Average package", get: (p) => (p.placements.avg_package_lpa != null ? `${p.placements.avg_package_lpa} LPA` : "—") },
      { label: "Highest package", get: (p) => (p.placements.highest_package_lpa != null ? `${p.placements.highest_package_lpa} LPA` : "—") },
      { label: "Top recruiters", get: (p) => p.placements.top_recruiters ?? "—" },
    ],
  },
  {
    key: "fees",
    title: "Annual Fees by Category",
    icon: <Wallet className="h-4 w-4" />,
    rows: FEE_CATS.map((cat) => ({
      label: cat,
      get: (p: CollegeProfile) => fmtFee(p.fees[cat]),
    })),
  },
  {
    key: "facilities",
    title: "Facilities",
    icon: <Landmark className="h-4 w-4" />,
    rows: [
      { label: "Campus size", get: (p) => (p.facilities.campus_area_acres != null ? `${p.facilities.campus_area_acres} acres` : "—") },
      { label: "Wi-Fi campus", get: (p) => yesNo(p.facilities.wifi) },
      { label: "Boys hostel", get: (p) => yesNo(p.facilities.hostel_boys) },
      { label: "Girls hostel", get: (p) => yesNo(p.facilities.hostel_girls) },
      { label: "Sports facilities", get: (p) => yesNo(p.facilities.sports) },
    ],
  },
  {
    key: "contact",
    title: "Location & Contact",
    icon: <MapPin className="h-4 w-4" />,
    rows: [
      { label: "Address", get: (p) => p.location.address ?? "—" },
      { label: "Website", get: (p) => p.contact.website_url ?? "—" },
      { label: "Phone", get: (p) => p.contact.phone ?? "—" },
      { label: "Email", get: (p) => p.contact.email ?? "—" },
    ],
  },
];

// ── URL <-> compare-list helpers ───────────────────────────────────────────────

function parseCodes(raw: string | null): string[] {
  const codes = (raw ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  return Array.from(new Set(codes)).slice(0, MAX_COMPARE);
}

// ── Add-college slot (inline search) ───────────────────────────────────────────

function AddSlot({
  excludeCodes,
  onPick,
}: {
  excludeCodes: string[];
  onPick: (college: CompareCollege) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ college_code: string; college_name: string; city: string | null }[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchColleges(q, undefined, undefined, 8);
        setResults(data.filter((r) => !excludeCodes.includes(r.college_code)));
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q, excludeCodes]);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setQ("");
      }
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex flex-col items-center justify-center gap-2 rounded-[13px] border-2 border-dashed h-full min-h-[180px] transition-colors hover:bg-[var(--ep-surface)]"
        style={{ borderColor: "var(--ep-border-strong)" }}
      >
        <Plus className="h-6 w-6 text-ep-muted" />
        <span className="text-sm font-medium text-ep-muted">Add college</span>
      </button>
    );
  }

  return (
    <div ref={ref} className="relative rounded-[13px] border p-3 min-h-[180px]" style={{ background: "var(--ep-surface)", borderColor: "var(--color-ep-primary)" }}>
      <div className="flex items-center gap-2 rounded-[8px] border px-2.5 py-1.5" style={{ borderColor: "var(--ep-border)", background: "var(--ep-input)" }}>
        <Search className="h-3.5 w-3.5 text-ep-muted shrink-0" />
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search colleges..."
          className="bg-transparent text-sm text-[var(--ep-text)] outline-none placeholder:text-ep-muted w-full"
        />
      </div>
      {(loading || results.length > 0) && (
        <div className="absolute left-0 right-0 top-[52px] z-30 mt-1 rounded-[8px] border shadow-lg max-h-60 overflow-y-auto" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
          {loading && <p className="px-3 py-2.5 text-xs text-ep-muted">Searching…</p>}
          {!loading &&
            results.map((r) => (
              <button
                key={r.college_code}
                onClick={() => {
                  onPick({ code: r.college_code, name: r.college_name });
                  setOpen(false);
                  setQ("");
                }}
                className="w-full text-left px-3 py-2.5 border-b last:border-0 hover:bg-[var(--ep-bg)] transition-colors"
                style={{ borderColor: "var(--ep-border)" }}
              >
                <p className="text-[13px] font-semibold text-[var(--ep-text)] leading-snug truncate">{r.college_name}</p>
                <p className="text-[11px] text-ep-muted mt-0.5">{r.city ?? "Maharashtra"}</p>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}

// ── College card (top sticky row) ──────────────────────────────────────────────

function CollegeCard({ profile, onRemove }: { profile: CollegeProfile; onRemove: () => void }) {
  const thumb = profile.images[0]?.url;
  return (
    <div className="relative rounded-[13px] border overflow-hidden flex flex-col" style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}>
      <button
        onClick={onRemove}
        aria-label={`Remove ${profile.college_name}`}
        className="absolute top-2 right-2 z-10 h-6 w-6 rounded-full flex items-center justify-center text-white transition-opacity hover:opacity-90"
        style={{ background: "rgba(0,0,0,0.45)" }}
      >
        <X className="h-3.5 w-3.5" />
      </button>
      <div className="h-24 w-full shrink-0" style={{ background: "linear-gradient(135deg, #DCE3EC, #C6D2DF)" }}>
        {thumb && (
          <img
            src={googleImageUrl(thumb, "thumb")}
            alt={profile.college_name}
            referrerPolicy="no-referrer"
            className="w-full h-full object-cover"
          />
        )}
      </div>
      <div className="p-3 flex-1 flex flex-col gap-1.5">
        <Link
          href={`/colleges/${profile.college_code}`}
          className="font-serif text-[14px] font-medium leading-snug hover:underline line-clamp-2"
          style={{ color: "var(--color-ep-primary)" }}
        >
          {profile.college_name}
        </Link>
        <div className="flex items-center gap-1.5 flex-wrap mt-auto pt-1">
          {profile.score.overall != null && (
            <span
              className="font-mono inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-1 rounded-[6px] border text-[var(--ep-text)]"
              style={{ borderColor: "var(--ep-border)" }}
            >
              <Star className="h-2.5 w-2.5" fill="var(--color-ep-amber)" stroke="var(--color-ep-amber)" />
              {profile.score.overall}/100
            </span>
          )}
          {profile.accreditation.naac_grade && (
            <Badge variant="safe" className="text-[10px] px-1.5 py-0.5">
              NAAC {profile.accreditation.naac_grade}
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}

function CardSkeleton() {
  return <Skeleton className="rounded-[13px] min-h-[180px] w-full" />;
}

function CardError({ code, onRemove }: { code: string; onRemove: () => void }) {
  return (
    <div className="relative rounded-[13px] border-2 border-dashed p-4 min-h-[180px] flex flex-col items-center justify-center gap-2 text-center" style={{ borderColor: "var(--color-ep-red-border)" }}>
      <AlertTriangle className="h-5 w-5" style={{ color: "var(--color-ep-red)" }} />
      <p className="text-xs text-ep-muted">Could not load {code}</p>
      <button onClick={onRemove} className="text-xs font-semibold hover:underline" style={{ color: "var(--color-ep-primary)" }}>
        Remove
      </button>
    </div>
  );
}

// ── Comparison row ──────────────────────────────────────────────────────────────

function CompareRow({
  row,
  slotProfiles,
  factsByCode,
  columnCount,
  highlight,
}: {
  row: Row;
  /** One entry per code SLOT (not per loaded profile) — null = still loading or
   * errored — so a cell's column position always matches its college's card,
   * even when colleges resolve out of order or one fails to load. */
  slotProfiles: (CollegeProfile | null)[];
  factsByCode: Map<string, DerivedFacts>;
  columnCount: number;
  highlight: boolean;
}) {
  const values = slotProfiles.map((p) => (p ? row.get(p, factsByCode.get(p.college_code)!) : null));
  const loadedValues = values.filter((v): v is string => v != null);
  const allSame = loadedValues.length > 0 && loadedValues.every((v) => v === loadedValues[0]);

  return (
    <div
      className="grid border-b last:border-0"
      style={{ gridTemplateColumns: `200px repeat(${columnCount}, minmax(180px,1fr))`, borderColor: "var(--ep-border)" }}
    >
      <div className="py-3 px-4 text-[12.5px] font-medium text-[var(--ep-text-secondary)] flex items-center">
        {row.label}
      </div>
      {slotProfiles.map((p, i) => (
        <div
          key={p?.college_code ?? `pending-${i}`}
          title={values[i] ?? undefined}
          className={cn(
            "py-3 px-4 text-[13px] truncate flex items-center",
            values[i] == null ? "text-ep-muted italic" : "text-[var(--ep-text)]",
            highlight && !allSame && values[i] != null && "font-semibold"
          )}
          style={highlight && !allSame && values[i] != null ? { background: "var(--color-ep-amber-tint)" } : undefined}
        >
          {values[i] ?? "…"}
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <ComparePageInner />
    </Suspense>
  );
}

function ComparePageInner() {
  const searchParams = useSearchParams();
  const compare = useCompare();
  // `codes` is local state (seeded once from the URL), NOT derived live from
  // useSearchParams(). Add/remove used to call router.push() with a new query
  // string and rely on useSearchParams() picking it up — but on this Next.js
  // version, router.push()/replace() to the SAME pathname with only the
  // search string changed silently no-ops (confirmed: router.push received
  // the correct new URL, but the address bar and useSearchParams() never
  // updated — add-college and remove-card appeared completely broken).
  // Driving the UI off local state makes every add/remove instantly correct
  // regardless of the router; the address bar is kept in sync separately via
  // the raw History API (see setCodes below), bypassing the router entirely.
  const [codes, setCodesState] = useState<string[]>(() => parseCodes(searchParams.get("codes")));

  // A bare /compare visit (nav link, bookmark) carries no ?codes= — fall back
  // to the floating-tray list once it hydrates, otherwise a counsellor with a
  // full tray lands on "Add at least 2 colleges" despite the nav badge. Runs
  // once, and only when the URL contributed nothing (shared links still win).
  const seededFromTrayRef = useRef(false);
  useEffect(() => {
    if (seededFromTrayRef.current || !compare.hydrated) return;
    seededFromTrayRef.current = true;
    if (codes.length === 0 && compare.items.length > 0) {
      const trayCodes = compare.items.map((c) => c.code).slice(0, MAX_COMPARE);
      setCodesState(trayCodes);
      window.history.replaceState(null, "", `/compare?codes=${trayCodes.join(",")}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compare.hydrated]);

  const results = useQueries({
    queries: codes.map((code) => ({
      queryKey: ["college", code],
      queryFn: () => getCollegeProfile(code),
      staleTime: 10 * 60 * 1000,
      retry: false,
    })),
  }) as UseQueryResult<CollegeProfile>[];

  const profiles = results.map((r) => r.data).filter((d): d is CollegeProfile => !!d);
  // Same length/order as `codes` — keeps every data-row cell aligned with its
  // college's card in the sticky row above, even mid-load or on a 404.
  const slotProfiles = useMemo(() => codes.map((_, i) => results[i]?.data ?? null), [codes, results]);
  const factsByCode = useMemo(() => {
    const m = new Map<string, DerivedFacts>();
    for (const p of profiles) m.set(p.college_code, deriveFacts(p));
    return m;
  }, [profiles]);

  const [highlight, setHighlight] = useState(true);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  // Keep the global compare tray in sync with whatever this page is showing —
  // so a shared /compare?codes=... link "just works" and removing a card here
  // also drops it from the floating tray elsewhere in the app.
  const syncedRef = useRef<string>("");
  useEffect(() => {
    if (!compare.hydrated || profiles.length === 0) return;
    const key = profiles.map((p) => p.college_code).sort().join(",");
    if (syncedRef.current === key) return;
    syncedRef.current = key;
    for (const p of profiles) {
      if (!compare.isComparing(p.college_code)) {
        compare.add({ code: p.college_code, name: p.college_name });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profiles, compare.hydrated]);

  function setCodes(next: string[]) {
    setCodesState(next);
    // Sync the address bar via the raw History API, not router.replace(): on
    // this Next.js version router.replace()/push() to the SAME pathname with
    // only the query string changed is a silent no-op (confirmed — it never
    // updates window.location or useSearchParams()). Since rendering no
    // longer depends on the router for this (see `codes` state above), a
    // direct history.replaceState keeps the link shareable without needing
    // Next's client router to cooperate.
    const url = next.length ? `/compare?codes=${next.join(",")}` : "/compare";
    window.history.replaceState(null, "", url);
  }

  function removeCode(code: string) {
    compare.remove(code);
    setCodes(codes.filter((c) => c !== code));
  }

  function addCode(college: CompareCollege) {
    compare.add(college);
    setCodes([...codes, college.code]);
  }

  const toggleSection = (key: string) => setCollapsed((s) => ({ ...s, [key]: !s[key] }));

  const showAddSlot = codes.length < MAX_COMPARE;
  const columnCount = codes.length + (showAddSlot ? 1 : 0);
  // Show the comparison grid as soon as enough slots are ATTEMPTED (not just
  // loaded) so the layout appears immediately with per-cell loading placeholders,
  // rather than the whole section waiting on the slowest network request.
  const readyToCompare = codes.length >= MIN_COMPARE;

  return (
    <div className="min-h-screen pb-24" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="font-mono text-xs uppercase mb-1.5" style={{ letterSpacing: "0.14em", color: "var(--color-ep-green)" }}>
              Compare
            </div>
            <h1 className="font-display text-[32px] leading-[1.1] text-[var(--ep-text)] flex items-center gap-2.5">
              <GitCompareArrows className="h-7 w-7" style={{ color: "var(--color-ep-primary)" }} />
              College Compare
            </h1>
          </div>
          {readyToCompare && (
            <label className="flex items-center gap-2 text-sm font-medium text-[var(--ep-text-secondary)] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={highlight}
                onChange={(e) => setHighlight(e.target.checked)}
                className="h-4 w-4 rounded accent-[var(--color-ep-primary)]"
              />
              Highlight differences
            </label>
          )}
        </div>

        {/* Sticky card row.
            NOTE: this grid's gridTemplateColumns MUST stay pixel-identical to
            every CompareRow's grid below (same column widths, ZERO gap on
            both) or the cards visibly drift out of alignment with their data
            columns as more colleges are added — this happened once already
            (gap-3 here vs no gap on data rows compounded ~12px per column).
            Visual spacing between cards comes from padding INSIDE each cell
            (below), never from a grid gap.
            NO overflow-x-auto wrapper here on purpose: per the CSS Overflow
            spec, setting overflow-x to anything but visible forces the OTHER
            axis's computed overflow to auto too (you cannot keep overflow-y
            "visible" once overflow-x isn't) — confirmed via computed style,
            explicit `overflow-y-visible` did NOT override it. That auto-y
            makes this div a scroll container, which becomes the containing
            block for `position: sticky` INSTEAD of the page, so the card row
            renders already-"stuck" and overlaps the section below it even at
            scroll position zero. Letting the (rare, only when >3 wide columns
            on a narrow viewport) horizontal overflow fall through to the page
            itself avoids creating that inner scroll container. */}
        <div>
          <div style={{ minWidth: 200 + columnCount * 200 }}>
            <div
              className="sticky z-20 pb-4"
              style={{ top: 73, background: "var(--ep-bg)" }}
            >
              <div
                className="grid"
                style={{ gridTemplateColumns: `200px repeat(${columnCount}, minmax(180px,1fr))` }}
              >
                <div />
                {codes.map((code, i) => {
                  const r = results[i];
                  if (r.isLoading) return <div key={code} className="px-1.5"><CardSkeleton /></div>;
                  if (r.isError || !r.data) return <div key={code} className="px-1.5"><CardError code={code} onRemove={() => removeCode(code)} /></div>;
                  return <div key={code} className="px-1.5"><CollegeCard profile={r.data} onRemove={() => removeCode(code)} /></div>;
                })}
                {showAddSlot && (
                  <div key="add-slot" className="px-1.5">
                    <AddSlot excludeCodes={codes} onPick={addCode} />
                  </div>
                )}
              </div>
            </div>

            {!readyToCompare && (
              <div className="rounded-[10px] border px-5 py-4 text-sm flex items-center gap-3 mt-2" style={{ borderColor: "var(--ep-border)", background: "var(--ep-surface)" }}>
                <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: "var(--color-ep-amber)" }} />
                <span className="text-[var(--ep-text-secondary)]">
                  Add at least {MIN_COMPARE} colleges to see the side-by-side comparison.
                </span>
              </div>
            )}

            {readyToCompare && (
              <div className="mt-2 rounded-[13px] border overflow-hidden" style={{ borderColor: "var(--ep-border)" }}>
                {SECTIONS.map((section) => {
                  const isCollapsed = !!collapsed[section.key];
                  return (
                    <div key={section.key} className="border-b last:border-0" style={{ borderColor: "var(--ep-border)" }}>
                      <button
                        onClick={() => toggleSection(section.key)}
                        className="w-full flex items-center gap-2 px-4 py-3 transition-colors hover:bg-[var(--ep-bg)]"
                        style={{ background: "var(--ep-surface)" }}
                      >
                        {isCollapsed ? (
                          <ChevronRight className="h-3.5 w-3.5 text-ep-muted" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5 text-ep-muted" />
                        )}
                        <span style={{ color: "var(--color-ep-primary)" }}>{section.icon}</span>
                        <span className="font-semibold text-[13px] text-[var(--ep-text)]">{section.title}</span>
                      </button>
                      {!isCollapsed &&
                        section.rows.map((row) => (
                          <CompareRow
                            key={row.label}
                            row={row}
                            slotProfiles={slotProfiles}
                            factsByCode={factsByCode}
                            columnCount={columnCount}
                            highlight={highlight}
                          />
                        ))}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
