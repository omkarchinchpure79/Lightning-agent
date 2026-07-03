"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Building2,
  ChevronRight,
  SlidersHorizontal,
  X,
  GraduationCap,
  Landmark,
  Building,
  Star,
  ArrowRight,
} from "lucide-react";

import { searchColleges, fetchBranchKeywords, type CollegeSearchResult } from "@/lib/api";
import { NavHeader } from "@/components/NavHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { DiscoveryFilters, type SidebarFilterState } from "@/components/DiscoveryFilters";

// ── Types ──────────────────────────────────────────────────────────────────────

type FilterId =
  | "all"
  | "government"
  | "private"
  | "naac_a";

interface FilterPill {
  id: FilterId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** If set, pass as institution_type param to the API */
  apiType?: string;
  /** If true, pass naac_above_a=true to the API */
  naacFilter?: boolean;
}

interface ComingSoonPill {
  label: string;
}

const FILTER_PILLS: FilterPill[] = [
  { id: "all",        label: "All Colleges",          icon: GraduationCap },
  { id: "government", label: "Government",             icon: Landmark, apiType: "gov" },
  { id: "private",    label: "Private",                icon: Building, apiType: "pvt" },
  { id: "naac_a",     label: "NAAC A & Above",         icon: Star, naacFilter: true },
];

// Top Placements: only 15/713 colleges have placement_pct data (2% coverage) — unusable as a filter.
// Engineering & Tech: every college in MHT CET CAP is an engineering college — filter would be universal.
const COMING_SOON_PILLS: ComingSoonPill[] = [
  { label: "Top Placements" },
  { label: "Engineering & Tech" },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function institutionLabel(type: string | null): string | null {
  if (!type) return null;
  const t = type.toLowerCase();
  if (t.includes("gov")) return "Government";
  if (t.includes("aided")) return "Government-Aided";
  if (t.includes("pvt") || t.includes("priv")) return "Private";
  return type;
}

function applyClientFilter(
  colleges: CollegeSearchResult[],
  searchQ: string
): CollegeSearchResult[] {
  if (!searchQ.trim()) return colleges;
  const q = searchQ.toLowerCase();
  return colleges.filter(
    (c) =>
      c.college_name.toLowerCase().includes(q) ||
      (c.city ?? "").toLowerCase().includes(q) ||
      (c.district ?? "").toLowerCase().includes(q)
  );
}

// ── Editorial list row ────────────────────────────────────────────────────────

function CollegeRow({ college, index }: { college: CollegeSearchResult; index: number }) {
  const router = useRouter();
  const meta = [college.city, institutionLabel(college.institution_type), college.naac_grade ? `NAAC ${college.naac_grade}` : null]
    .filter(Boolean)
    .join(" · ") || "Maharashtra";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      onClick={() => router.push(`/colleges/${college.college_code}`)}
      className="flex items-center gap-5 py-5 px-1.5 border-b cursor-pointer transition-colors hover:bg-[var(--ep-surface)]"
      style={{ borderColor: "var(--ep-border)" }}
    >
      <span
        className="font-display shrink-0 w-10 text-[22px] leading-none"
        style={{ color: "#B7B1A2" }}
      >
        {String(index + 1).padStart(2, "0")}
      </span>
      <div
        className="h-[9px] w-[9px] rounded-full shrink-0"
        style={{ background: index === 0 ? "var(--color-ep-green)" : "var(--color-ep-primary)" }}
      />
      <div className="flex-1 min-w-0">
        <div className="font-serif text-[19px] font-medium text-[var(--ep-text)] truncate">
          {college.college_name}
        </div>
        <div className="text-xs text-ep-muted mt-0.5 truncate">{meta}</div>
      </div>
      {college.score != null && (
        <div className="text-right w-[100px] shrink-0">
          <div className="font-mono text-xl font-semibold text-[var(--ep-text)]">
            {college.score.toFixed(0)}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-wide" style={{ color: "#9A968B" }}>
            score
          </div>
        </div>
      )}
      <ChevronRight className="h-4 w-4 shrink-0" style={{ color: "#C4BCA9" }} />
    </motion.div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

export default function HomePage() {
  const [allColleges, setAllColleges]   = useState<CollegeSearchResult[]>([]);
  const [loading, setLoading]           = useState(true);
  const [loadingMore, setLoadingMore]   = useState(false);
  const [hasMore, setHasMore]           = useState(true);
  const [offset, setOffset]             = useState(0);

  const [searchQ, setSearchQ]           = useState("");
  const [sidebarFilters, setSidebarFilters] = useState<SidebarFilterState>({});
  const [naacAboveA, setNaacAboveA]     = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [heroBranchOptions, setHeroBranchOptions] = useState<string[]>([]);

  useEffect(() => {
    fetchBranchKeywords().then(setHeroBranchOptions).catch(() => {});
  }, []);

  const activeFilter: FilterId = naacAboveA
    ? "naac_a"
    : sidebarFilters.institutionType === "gov"
    ? "government"
    : sidebarFilters.institutionType === "pvt"
    ? "private"
    : "all";

  async function loadPage(
    pageOffset: number,
    replace = false,
    filters: SidebarFilterState = sidebarFilters,
    naacFlag: boolean = naacAboveA,
  ) {
    if (pageOffset === 0) setLoading(true);
    else setLoadingMore(true);

    try {
      const page = await searchColleges(
        "", filters.district, filters.institutionType, PAGE_SIZE, pageOffset, naacFlag,
        {
          naacGrade: filters.naacGrade,
          branch: filters.branch,
          scoreMin: filters.scoreMin,
          scoreMax: filters.scoreMax,
        }
      );
      setAllColleges((prev) => replace ? page : [...prev, ...page]);
      setOffset(pageOffset + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } catch {
      // leave list as-is; no crash
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => { loadPage(0, true, {}, false); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleFilterClick(pill: FilterPill) {
    const naac = pill.naacFilter ?? false;
    const nextFilters: SidebarFilterState = {
      ...sidebarFilters,
      institutionType: pill.apiType,
      naacGrade: naac ? undefined : sidebarFilters.naacGrade,
    };
    setSidebarFilters(nextFilters);
    setNaacAboveA(naac);
    setOffset(0);
    loadPage(0, true, nextFilters, naac);
  }

  function handleSidebarChange(next: SidebarFilterState) {
    // Selecting a specific NAAC grade supersedes the "A & Above" quick pill.
    const nextNaac = next.naacGrade ? false : naacAboveA;
    setSidebarFilters(next);
    setNaacAboveA(nextNaac);
    setOffset(0);
    loadPage(0, true, next, nextNaac);
  }

  function clearAllFilters() {
    setSidebarFilters({});
    setNaacAboveA(false);
    setSearchQ("");
    setOffset(0);
    loadPage(0, true, {}, false);
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    // Text search filters client-side against loaded colleges.
    // Full cross-all-colleges search would require a backend call.
  }

  const filtered = useMemo(
    () => applyClientFilter(allColleges, searchQ),
    [allColleges, searchQ]
  );

  const hasAnyFilter = Boolean(
    searchQ.trim() || naacAboveA || sidebarFilters.institutionType ||
    sidebarFilters.district || sidebarFilters.naacGrade || sidebarFilters.branch ||
    sidebarFilters.scoreMin != null || sidebarFilters.scoreMax != null
  );

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <div className="relative overflow-hidden px-10 pt-16 pb-8" style={{ background: "var(--ep-bg)" }}>
        <svg
          viewBox="0 0 1160 400"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          <path
            d="M100 380 C 140 140, 380 80, 1080 110"
            fill="none"
            stroke="#DED8CA"
            strokeWidth="2"
            strokeDasharray="2 9"
            strokeLinecap="round"
          />
        </svg>
        <div className="relative max-w-3xl mx-auto sm:mx-0">
          <div
            className="font-mono text-xs uppercase mb-5"
            style={{ letterSpacing: "0.18em", color: "var(--color-ep-green)" }}
          >
            Guidance Platform · MHT CET
          </div>
          <h1 className="font-display text-[42px] sm:text-[58px] leading-[1.03] text-[var(--ep-text)] mb-5">
            Every student has a<br />
            <span className="italic" style={{ color: "var(--color-ep-primary)" }}>path.</span> We help you find it.
          </h1>
          <p className="text-[17px] leading-relaxed text-[#5B6472] mb-7 max-w-xl">
            From a single percentile to a confident admission — mapped with eleven years of real CAP cutoff data.
          </p>

          <form onSubmit={handleSearch} className="max-w-xl">
            <div
              className="flex items-center gap-3 pb-3 border-b-[1.5px]"
              style={{ borderColor: "var(--ep-text)" }}
            >
              <Search className="h-[18px] w-[18px] shrink-0" style={{ color: "var(--ep-text)" }} />
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="Search a college, city, or code…"
                className="flex-1 bg-transparent text-base outline-none placeholder:text-[#9A968B] text-[var(--ep-text)]"
              />
              <button type="submit" className="text-sm font-medium text-[var(--ep-text)] flex items-center gap-1 shrink-0">
                Explore <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>

          <div className="flex items-center gap-6 mt-6 text-[13px] text-[#7A7568] flex-wrap">
            <span>
              <b className="font-mono text-[15px] font-semibold text-[var(--ep-text)]">{allColleges.length || 713}</b> colleges
            </span>
            <span style={{ color: "#CFC9BA" }}>·</span>
            <span>
              <b className="font-mono text-[15px] font-semibold text-[var(--ep-text)]">11 yrs</b> cutoff data
            </span>
            <span style={{ color: "#CFC9BA" }}>·</span>
            <span>
              <b className="font-mono text-[15px] font-semibold text-[var(--ep-text)]">36</b> districts
            </span>
          </div>
        </div>
      </div>

      {/* Branch quick-filter (real, backed by the branches table join in /api/colleges/search) */}
      <div className="border-t border-b px-10 py-3.5" style={{ borderColor: "var(--ep-border)" }}>
        <div className="max-w-7xl mx-auto flex items-center gap-2">
          <GraduationCap className="h-4 w-4 shrink-0" style={{ color: "#9A968B" }} />
          <select
            value={sidebarFilters.branch ?? ""}
            onChange={(e) => handleSidebarChange({ ...sidebarFilters, branch: e.target.value || undefined })}
            className="bg-transparent text-sm text-[var(--ep-text)] outline-none cursor-pointer"
          >
            <option value="">Any branch</option>
            {heroBranchOptions.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Filter chips ───────────────────────────────────────────────────── */}
      <div className="border-b px-10 py-3.5" style={{ borderColor: "var(--ep-border)" }}>
        <div className="max-w-7xl mx-auto flex items-center gap-2 flex-wrap">
          {FILTER_PILLS.map((pill) => {
            const active = activeFilter === pill.id;
            const Icon = pill.icon;
            return (
              <motion.button
                key={pill.id}
                whileTap={{ scale: 0.96 }}
                onClick={() => handleFilterClick(pill)}
                className="flex items-center gap-1.5 px-[15px] py-2 rounded-full text-[13px] font-medium whitespace-nowrap border transition-colors"
                style={
                  active
                    ? { borderColor: "var(--color-ep-primary)", color: "var(--color-ep-primary)", background: "rgba(30,77,140,.06)", fontWeight: 600 }
                    : { borderColor: "var(--ep-border-strong)", color: "#4A5462" }
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {pill.label}
                {loading && active && (
                  <span className="ml-1 h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin inline-block" />
                )}
              </motion.button>
            );
          })}
          {COMING_SOON_PILLS.map((pill) => (
            <span
              key={pill.label}
              className="flex items-center gap-1.5 px-[15px] py-2 rounded-full text-[13px] font-medium whitespace-nowrap border border-dashed select-none"
              style={{ borderColor: "var(--ep-border-strong)", color: "#B0A99A" }}
              title="Coming soon"
            >
              {pill.label}
              <span
                className="font-mono text-[9px] font-semibold px-[5px] py-[2px] rounded"
                style={{ letterSpacing: "0.05em", background: "#F0E9D6", color: "var(--color-ep-amber-ink)" }}
              >
                SOON
              </span>
            </span>
          ))}
          <span className="ml-auto font-mono text-xs" style={{ color: "#8A867B" }}>
            Sort ▾ Score
          </span>
        </div>
      </div>

      {/* ── Main content: sidebar + editorial list ───────────────────────────── */}
      <main className="mx-auto max-w-7xl px-10 py-8">
        <div className="flex items-start gap-8">
          {/* Desktop sidebar */}
          <aside
            className="hidden sm:block w-64 shrink-0 sticky rounded-[13px] border p-5"
            style={{ top: 88, background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
          >
            <DiscoveryFilters value={sidebarFilters} onChange={handleSidebarChange} />
          </aside>

          {/* Mobile filter drawer */}
          <AnimatePresence>
            {mobileFiltersOpen && (
              <>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 bg-black/40 z-40 sm:hidden"
                  onClick={() => setMobileFiltersOpen(false)}
                />
                <motion.div
                  initial={{ x: "-100%" }}
                  animate={{ x: 0 }}
                  exit={{ x: "-100%" }}
                  transition={{ type: "tween", duration: 0.2 }}
                  className="fixed inset-y-0 left-0 w-[85vw] max-w-sm z-50 sm:hidden p-5 overflow-y-auto"
                  style={{ background: "var(--ep-surface)" }}
                >
                  <DiscoveryFilters
                    value={sidebarFilters}
                    onChange={handleSidebarChange}
                    onClose={() => setMobileFiltersOpen(false)}
                    resultCount={allColleges.length}
                  />
                </motion.div>
              </>
            )}
          </AnimatePresence>

          {/* List column */}
          <div className="flex-1 min-w-0">
            {/* Mobile "Filters" button */}
            <button
              onClick={() => setMobileFiltersOpen(true)}
              className="sm:hidden mb-5 flex items-center gap-2 px-4 py-2 rounded-[10px] border text-sm font-medium text-[var(--ep-text)]"
              style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Filters
            </button>

            <div className="flex items-baseline justify-between mb-1">
              <span className="font-display text-[26px] text-[var(--ep-text)]">
                {loading
                  ? "Loading…"
                  : searchQ
                  ? `${filtered.length} result${filtered.length !== 1 ? "s" : ""}`
                  : `${allColleges.length}${hasMore ? "+" : ""} colleges`}
              </span>
              <div className="flex items-center gap-4">
                {hasAnyFilter && (
                  <button
                    onClick={clearAllFilters}
                    className="text-xs text-ep-muted hover:text-[var(--ep-text)] underline flex items-center gap-1"
                  >
                    <X className="h-3 w-3" />
                    Clear filters
                  </button>
                )}
                <span
                  className="font-mono text-[11px] uppercase hidden sm:inline"
                  style={{ letterSpacing: "0.06em", color: "#9A968B" }}
                >
                  sorted by score
                </span>
              </div>
            </div>

            {loading ? (
              <div className="space-y-3 mt-6">
                {[...Array(8)].map((_, i) => (
                  <Skeleton key={i} className="h-[76px] rounded-[10px]" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16 text-ep-muted">
                <Building2 className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p className="text-sm">No colleges matched your search.</p>
                <button
                  onClick={clearAllFilters}
                  className="mt-3 text-xs hover:underline"
                  style={{ color: "var(--color-ep-primary)" }}
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <>
                <AnimatePresence mode="popLayout">
                  <div>
                    {filtered.map((c, i) => (
                      <CollegeRow key={c.college_code} college={c} index={i} />
                    ))}
                  </div>
                </AnimatePresence>
                {hasMore && !searchQ.trim() && (
                  <div className="flex justify-center pt-6">
                    <button
                      onClick={() => loadPage(offset)}
                      disabled={loadingMore}
                      className="px-6 py-2.5 rounded-[10px] border text-sm font-medium text-[var(--ep-text-secondary)] hover:bg-[var(--ep-surface)] transition-colors disabled:opacity-50"
                      style={{ borderColor: "var(--ep-border)" }}
                    >
                      {loadingMore ? "Loading…" : `Load more (${allColleges.length} loaded)`}
                    </button>
                  </div>
                )}
              </>
            )}

            {/* Predictor CTA band */}
            <div
              className="relative overflow-hidden mt-8 rounded-[16px] px-9 py-8 flex items-center justify-between gap-6 flex-wrap"
              style={{ background: "#14213A" }}
            >
              <svg
                viewBox="0 0 900 160"
                preserveAspectRatio="none"
                className="pointer-events-none absolute inset-0 h-full w-full opacity-50"
                aria-hidden="true"
              >
                <path
                  d="M40 140 C 120 40, 500 30, 880 40"
                  fill="none"
                  stroke="#2C3A57"
                  strokeWidth="2"
                  strokeDasharray="2 9"
                  strokeLinecap="round"
                />
              </svg>
              <div className="relative">
                <div className="font-display text-2xl mb-1" style={{ color: "#F5F3EE" }}>
                  Ready for personalised matches?
                </div>
                <div className="text-sm max-w-xl" style={{ color: "#9BA6BA" }}>
                  Enter a student&apos;s percentile and category to get SAFE / PROBABLE / REACH predictions across every branch.
                </div>
              </div>
              <Link
                href="/students/new"
                className="relative flex items-center gap-2 px-6 py-3.5 rounded-[11px] text-sm font-semibold whitespace-nowrap transition-opacity hover:opacity-90"
                style={{ background: "var(--color-ep-green)", color: "#0E1729" }}
              >
                Get predictions
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
