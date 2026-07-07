"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapPin,
  Globe,
  Mail,
  Phone,
  Users,
  Wifi,
  Dumbbell,
  Building2,
  GraduationCap,
  TrendingUp,
  ExternalLink,
  AlertTriangle,
  ChevronLeft,
  Bookmark,
  X,
  Star,
  Lightbulb,
  RotateCcw,
  Sparkles,
  FileText,
  BarChart3,
  Wallet,
  Landmark,
  Images,
  Trophy,
  Check,
  Copy,
} from "lucide-react";

import {
  getCollegeProfile,
  getCollegeBranches,
  getCollegeDescription,
  generateCollegeDescription,
  type CollegeProfile,
  type CollegeFeeEntry,
} from "@/lib/api";
import { googleImageUrl, cn, fmtPercentile } from "@/lib/utils";
import { useShortlist } from "@/lib/useShortlist";
import { CompareButton } from "@/components/CompareButton";
import { NavHeader } from "@/components/NavHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtFee(fee: CollegeFeeEntry): string {
  if (!fee.available) return "Fee N/A";
  return `₹${(fee.total_annual ?? 0).toLocaleString("en-IN")}/yr`;
}

function Section({
  title,
  icon,
  children,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("rounded-[13px] border overflow-hidden", className)}
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
    >
      <div
        className="px-[18px] py-3 border-b flex items-center gap-2"
        style={{ borderColor: "var(--ep-border)" }}
      >
        {icon && <span style={{ color: "var(--color-ep-primary)" }}>{icon}</span>}
        <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function NotAvailable({ label }: { label: string }) {
  return (
    <p className="text-sm text-ep-muted italic">
      {label} data not available for this college.
    </p>
  );
}

// Click-to-copy code chip (college code, course code). Shows the official
// numeric code counsellors quote in CAP forms, and copies it verbatim.
function CopyableCode({
  code,
  label,
  className,
}: {
  code: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  async function handleCopy(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked — no-op */
    }
  }
  return (
    <button
      type="button"
      onClick={handleCopy}
      title={`Copy ${label ?? "code"} ${code}`}
      className={cn(
        "group inline-flex items-center gap-1.5 rounded-[7px] border px-2.5 py-1 font-mono text-[12px] font-medium transition-colors hover:bg-[var(--ep-bg)]",
        className
      )}
      style={{ borderColor: "var(--ep-border)", color: "var(--ep-text-secondary)" }}
    >
      {label && <span className="text-ep-muted not-italic">{label}</span>}
      <span className="text-[var(--ep-text)]">{code}</span>
      {copied ? (
        <Check className="h-3.5 w-3.5" style={{ color: "var(--color-ep-green)" }} />
      ) : (
        <Copy className="h-3.5 w-3.5 text-ep-muted group-hover:text-[var(--color-ep-primary)]" />
      )}
    </button>
  );
}

// ── Lightbox ───────────────────────────────────────────────────────────────────

function Lightbox({
  images,
  initialIndex,
  onClose,
}: {
  images: { url: string; caption?: string | null }[];
  initialIndex: number;
  onClose: () => void;
}) {
  const [idx, setIdx] = useState(initialIndex);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: "rgba(0,0,0,0.85)" }}
        onClick={onClose}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white opacity-70 hover:opacity-100"
          aria-label="Close"
        >
          <X className="h-7 w-7" />
        </button>

        <motion.div
          initial={{ scale: 0.94 }}
          animate={{ scale: 1 }}
          onClick={(e) => e.stopPropagation()}
          className="relative max-w-4xl w-full"
        >
          <img
            src={googleImageUrl(images[idx].url, "hero")}
            alt={images[idx].caption ?? `Image ${idx + 1}`}
            referrerPolicy="no-referrer"
            className="w-full max-h-[80vh] object-contain rounded-[8px]"
          />
          {images.length > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {images.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setIdx(i)}
                  className={`h-1.5 w-6 rounded-full transition-colors ${
                    i === idx ? "bg-white" : "bg-white/30"
                  }`}
                />
              ))}
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ── Hero image gallery (Airbnb-style) ─────────────────────────────────────────

// Warm-paper placeholder gradients for broken/empty tiles — alternate cool/warm
// so a mosaic of placeholders still reads as intentional, not "missing".
const COOL_GRADIENT = "linear-gradient(135deg, #DCE3EC, #C6D2DF)";
const WARM_GRADIENT = "linear-gradient(135deg, #E7ECF3, #D6DFEA)";

function PlaceholderTile({ cool, size = 34 }: { cool: boolean; size?: number }) {
  return (
    <div
      className="w-full h-full flex items-center justify-center"
      style={{ background: cool ? COOL_GRADIENT : WARM_GRADIENT }}
    >
      <Building2
        style={{ width: size, height: size, color: cool ? "#9DAEC0" : "#A8B6C7" }}
        strokeWidth={1.2}
      />
    </div>
  );
}

function HeroGallery({
  images,
  collegeName,
}: {
  images: CollegeProfile["images"];
  collegeName: string;
}) {
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const [heroFailed, setHeroFailed] = useState(false);
  const [thumbFailed, setThumbFailed] = useState<Record<number, boolean>>({});

  if (images.length === 0) {
    return (
      <div className="w-full rounded-[14px] overflow-hidden" style={{ height: 320 }}>
        <PlaceholderTile cool size={60} />
      </div>
    );
  }

  const hero = images[0];
  const thumbs = images.slice(1, 5);
  while (thumbs.length < 4) thumbs.push(hero);

  return (
    <>
      <div className="grid grid-cols-4 gap-2 rounded-[14px] overflow-hidden" style={{ height: 360 }}>
        {/* Large hero — 2 cols wide, full height */}
        <div
          className="col-span-2 row-span-2 relative cursor-pointer overflow-hidden"
          onClick={() => setLightboxIdx(0)}
        >
          {heroFailed ? (
            <PlaceholderTile cool size={60} />
          ) : (
            <img
              src={googleImageUrl(hero.url, "hero")}
              alt={hero.caption ?? collegeName}
              loading="eager"
              referrerPolicy="no-referrer"
              className="w-full h-full object-cover transition-transform hover:scale-105 duration-300"
              onError={() => setHeroFailed(true)}
            />
          )}
        </div>

        {/* 4 thumbnails (2×2) */}
        {thumbs.map((img, i) => {
          const isLastWithMore = i === 3 && images.length > 5;
          const failed = thumbFailed[i];
          return (
            <div
              key={i}
              className="relative cursor-pointer overflow-hidden"
              onClick={() => setLightboxIdx(i + 1 < images.length ? i + 1 : 0)}
            >
              {failed ? (
                <PlaceholderTile cool={i % 2 === 0} />
              ) : (
                <img
                  src={googleImageUrl(img.url, "gallery")}
                  alt={img.caption ?? `View ${i + 2}`}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  className="w-full h-full object-cover transition-transform hover:scale-105 duration-300"
                  onError={() => setThumbFailed((prev) => ({ ...prev, [i]: true }))}
                />
              )}
              {/* "+N more" overlay — always visible on last thumb, intentional dark gradient */}
              {isLastWithMore && (
                <div
                  className="absolute inset-0 flex items-center justify-center text-white text-sm font-semibold"
                  style={{ background: "linear-gradient(135deg, var(--color-ep-primary), #0E2A4D)" }}
                >
                  +{images.length - 4} more
                </div>
              )}
            </div>
          );
        })}
      </div>

      {lightboxIdx !== null && (
        <Lightbox
          images={images}
          initialIndex={lightboxIdx}
          onClose={() => setLightboxIdx(null)}
        />
      )}
    </>
  );
}

// ── AI Description (live endpoint, DB-cached) ──────────────────────────────────

function AIDescription({ code }: { code: string }) {
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError]     = useState<string | null>(null);

  // Try to fetch existing cached description
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["college-description", code],
    queryFn: () => getCollegeDescription(code),
    retry: false,          // 404 means "not generated yet" — don't retry
    staleTime: Infinity,   // cached descriptions don't change unless forced
  });

  async function handleGenerate(force = false) {
    setGenerating(true);
    setGenError(null);
    try {
      await generateCollegeDescription(code, force);
      refetch();
    } catch (e) {
      setGenError(e instanceof Error ? e.message : "Failed to generate description.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div
      className="rounded-[13px] border p-6"
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4" style={{ color: "var(--color-ep-green)" }} />
          <h2 className="font-semibold text-[13px] text-[var(--ep-text)]">
            About this college
          </h2>
          {data?.edited_by_counselor && (
            <span
              className="font-mono text-[10px] px-1.5 py-0.5 rounded font-medium"
              style={{ background: "var(--color-ep-amber-tint)", color: "var(--color-ep-amber-ink)" }}
            >
              Counsellor edited
            </span>
          )}
        </div>

        {/* Regenerate button (only shown once description exists) */}
        {data && !generating && (
          <button
            onClick={() => handleGenerate(true)}
            className="flex items-center gap-1 text-xs text-ep-muted hover:text-[var(--color-ep-primary)] transition-colors"
            title="Regenerate with Claude"
          >
            <RotateCcw className="h-3 w-3" />
            Regenerate
          </button>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-2">
          <div className="h-3 rounded bg-[var(--ep-border)] animate-pulse w-4/5" />
          <div className="h-3 rounded bg-[var(--ep-border)] animate-pulse w-3/5" />
          <div className="h-3 rounded bg-[var(--ep-border)] animate-pulse w-4/5" />
        </div>
      )}

      {/* Generating spinner */}
      {generating && (
        <p className="flex items-center gap-1.5 text-sm text-ep-muted animate-pulse">
          <Sparkles className="h-3.5 w-3.5" />
          Generating description with Claude…
        </p>
      )}

      {/* Description text */}
      {!isLoading && !generating && data && (
        <div className="font-serif text-[14.5px] leading-[1.65] text-[var(--ep-text-secondary)] whitespace-pre-line">
          {data.description}
        </div>
      )}

      {/* Not yet generated (404) */}
      {!isLoading && !generating && !data && !genError && (
        <div className="flex flex-col gap-3">
          <p className="flex items-center gap-1.5 text-sm text-ep-muted italic">
            <FileText className="h-3.5 w-3.5 not-italic shrink-0" />
            No description yet. Generate one with Claude AI.
          </p>
          <button
            onClick={() => handleGenerate(false)}
            className="self-start flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "var(--color-ep-primary)" }}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Generate Description
          </button>
        </div>
      )}

      {/* Error */}
      {genError && (
        <div
          className="rounded-[6px] border px-3 py-2 text-xs flex items-start gap-2 mt-2"
          style={{ borderColor: "var(--color-ep-red-border)", background: "var(--color-ep-red-tint)", color: "var(--color-ep-red-ink)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          {genError}
        </div>
      )}
    </div>
  );
}

// ── Sticky sidebar ────────────────────────────────────────────────────────────

function Sidebar({ profile }: { profile: CollegeProfile }) {
  const { toggle, isSaved } = useShortlist();
  const saved = isSaved(profile.college_code);
  const [toastVisible, setToastVisible] = useState(false);

  function handleToggle() {
    toggle({
      code: profile.college_code,
      name: profile.college_name,
      city: profile.location.district,
      score: profile.score.overall,
      institution_type: profile.identity.institution_type,
      imageUrl: profile.images[0]?.url ?? null,
    });
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2000);
  }

  return (
    <div
      className="rounded-[14px] border p-[18px] space-y-[11px] sticky top-20"
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
    >
      <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={handleToggle}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-[13px] font-semibold transition-all border",
          saved
            ? "border-[var(--color-ep-primary)] text-[var(--color-ep-primary)]"
            : "text-white"
        )}
        style={saved ? { background: "rgba(198,82,47,0.08)" } : { background: "var(--color-ep-primary)", borderColor: "var(--color-ep-primary)" }}
      >
        <Bookmark
          className="h-4 w-4 transition-all"
          fill={saved ? "var(--color-ep-primary)" : "none"}
          stroke="currentColor"
        />
        {saved ? "Saved" : "Save"}
      </motion.button>

      <CompareButton
        college={{ code: profile.college_code, name: profile.college_name }}
        variant="full"
      />

      {profile.contact.website_url && (
        <a
          href={profile.contact.website_url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-[13px] font-medium border text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)] transition-colors"
          style={{ borderColor: "var(--ep-border-strong)" }}
        >
          <Globe className="h-4 w-4" />
          Visit website
        </a>
      )}

      {profile.location.google_maps_url && (
        <a
          href={profile.location.google_maps_url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 py-3 rounded-[10px] text-[13px] font-medium border text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)] transition-colors"
          style={{ borderColor: "var(--ep-border-strong)" }}
        >
          <MapPin className="h-4 w-4" />
          View on Maps
        </a>
      )}

      <Link
        href="/my-shortlist"
        className="block text-center text-xs pt-1 hover:underline"
        style={{ color: "var(--color-ep-primary)" }}
      >
        View your full bookmarks →
      </Link>

      {/* Toast */}
      <AnimatePresence>
        {toastVisible && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            className="flex items-center justify-center gap-1.5 rounded-[8px] px-3 py-2 text-xs text-center font-medium"
            style={{ background: "var(--color-ep-green)", color: "white" }}
          >
            {saved && <Check className="h-3.5 w-3.5" />}
            {saved ? "Added to bookmarks" : "Removed from bookmarks"}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Profile view ───────────────────────────────────────────────────────────────

function CollegeProfileView({
  profile,
  code,
}: {
  profile: CollegeProfile;
  code: string;
}) {
  const { data: branchesData } = useQuery({
    queryKey: ["college-branches", code],
    queryFn: () => getCollegeBranches(code),
  });

  const { identity, accreditation, location, contact, facilities, placements, fees } = profile;

  const hasAnyFee = Object.values(fees).some((f) => f.available);
  const hasPlacementsData =
    placements.placement_pct != null || placements.avg_package_lpa != null;
  const hasFacilities =
    facilities.hostel_boys ||
    facilities.hostel_girls ||
    facilities.sports ||
    facilities.wifi;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
      {/* ── Left column ─────────────────────────────────────────────────────── */}
      <div className="space-y-6 min-w-0">
        {/* Hero gallery */}
        <HeroGallery images={profile.images} collegeName={profile.college_name} />

        {/* Title + stats */}
        <div>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="font-display text-[38px] leading-[1.08] text-[var(--ep-text)]">
                {profile.college_name}
              </h1>
              <p className="mt-2 text-sm text-ep-muted flex items-center gap-1.5">
                <MapPin className="h-[15px] w-[15px] shrink-0" />
                {[location.district, identity.institution_type]
                  .filter(Boolean)
                  .join(" · ")}
                {identity.year_established &&
                  ` · Est. ${identity.year_established}`}
              </p>
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <CopyableCode code={profile.college_code} label="Institute code" />
                {profile.paired_codes
                  ?.filter((c) => c !== profile.college_code)
                  .map((c) => (
                    <CopyableCode key={c} code={c} label="Also" />
                  ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-1">
              {accreditation.naac_grade && (
                <Badge variant="safe">NAAC {accreditation.naac_grade}</Badge>
              )}
              {identity.is_autonomous === 1 && (
                <Badge variant="muted">Autonomous</Badge>
              )}
              {profile.score.overall != null && (
                <span
                  className="font-mono inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-[7px] border text-[var(--ep-text)]"
                  style={{ borderColor: "var(--ep-border)" }}
                >
                  <Star className="h-[11px] w-[11px]" fill="var(--color-ep-amber)" stroke="var(--color-ep-amber)" />
                  {profile.score.overall}/100
                </span>
              )}
              {placements.placement_pct != null &&
                placements.placement_pct >= 80 && (
                  <Badge variant="safe">
                    <Trophy className="h-3 w-3 mr-1 -ml-0.5" />
                    Top Placements
                  </Badge>
                )}
            </div>
          </div>
        </div>

        {/* AI-generated description */}
        <AIDescription code={code} />

        {/* Quick facts */}
        <div
          className="rounded-[13px] border grid grid-cols-2 sm:grid-cols-4 overflow-hidden"
          style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
        >
          {[
            {
              label: "Established",
              value: identity.year_established?.toString() ?? "—",
              mono: true,
            },
            {
              label: "Campus size",
              value:
                facilities.campus_area_acres != null
                  ? `${facilities.campus_area_acres} acres`
                  : "N/A",
              mono: true,
            },
            {
              label: "University",
              value: location.affiliated_university ?? "—",
              mono: false,
            },
            {
              label: "NIRF Rank",
              value:
                accreditation.nirf_rank != null
                  ? `#${accreditation.nirf_rank}`
                  : "—",
              mono: true,
            },
          ].map(({ label, value, mono }, i) => (
            <div
              key={label}
              className="px-[18px] py-4 border-r last:border-r-0"
              style={{ borderColor: i === 3 ? "transparent" : "var(--ep-border)" }}
            >
              <p
                className="font-mono text-[10px] uppercase mb-1.5"
                style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
              >
                {label}
              </p>
              <p
                className={cn(
                  "text-[16px] font-semibold truncate",
                  mono && "font-mono",
                  value === "N/A" ? "text-ep-muted" : "text-[var(--ep-text)]"
                )}
                title={value}
              >
                {value}
              </p>
            </div>
          ))}
        </div>

        {/* Placements + Fees */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Section title="Placements" icon={<BarChart3 className="h-4 w-4" />}>
            {!hasPlacementsData ? (
              <p className="text-sm text-ep-muted">
                Placement data not available. Reach out to the counsellor for info.
              </p>
            ) : (
              <div className="space-y-4">
                {!placements.reliable && (
                  <div
                    className="flex items-center gap-2 rounded-[6px] border px-3 py-2 text-xs"
                    style={{ borderColor: "var(--color-ep-amber-border)", background: "var(--color-ep-amber-tint)", color: "var(--color-ep-amber-ink)" }}
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    Data may be outdated — verify with the college directly.
                  </div>
                )}
                <div className="grid grid-cols-3 gap-4">
                  {placements.placement_pct != null && (
                    <div>
                      <p className="text-[11px] text-ep-muted mb-0.5">Placement rate</p>
                      <p className="font-mono text-[22px] font-semibold text-[var(--ep-text)]">
                        {placements.placement_pct}%
                      </p>
                    </div>
                  )}
                  {placements.avg_package_lpa != null && (
                    <div>
                      <p className="text-[11px] text-ep-muted mb-0.5">Avg package</p>
                      <p className="font-mono text-[22px] font-semibold text-[var(--ep-text)]">
                        {placements.avg_package_lpa}
                        <span className="text-xs font-sans text-ep-muted"> LPA</span>
                      </p>
                    </div>
                  )}
                  {placements.highest_package_lpa != null && (
                    <div>
                      <p className="text-[11px] text-ep-muted mb-0.5">Highest</p>
                      <p className="font-mono text-[22px] font-semibold text-[var(--ep-text)]">
                        {placements.highest_package_lpa}
                        <span className="text-xs font-sans text-ep-muted"> LPA</span>
                      </p>
                    </div>
                  )}
                </div>
                {placements.top_recruiters && (
                  <div>
                    <p className="text-xs text-ep-muted mb-1">Top recruiters</p>
                    <p className="text-sm text-[var(--ep-text-secondary)]">
                      {placements.top_recruiters}
                    </p>
                  </div>
                )}
              </div>
            )}
          </Section>

          <Section title="Annual fees by category" icon={<Wallet className="h-4 w-4" />}>
            {!hasAnyFee ? (
              <p className="text-sm text-ep-muted">
                Fee data not available — ask the counsellor for details.
              </p>
            ) : (
              <div className="space-y-1">
                {(["GOPEN", "GOBC", "GSC", "TFWS"] as const).map((cat) => {
                  const fee = fees[cat];
                  return (
                    <div
                      key={cat}
                      className="flex items-center justify-between py-2 border-b last:border-0"
                      style={{ borderColor: "var(--ep-border)" }}
                    >
                      <span className="text-sm text-[var(--ep-text-secondary)]">
                        {cat}
                      </span>
                      <div className="text-right">
                        <span
                          className={cn(
                            "font-mono text-sm font-semibold",
                            fee.available
                              ? "text-[var(--ep-text)]"
                              : "text-ep-muted"
                          )}
                        >
                          {fmtFee(fee)}
                        </span>
                        {fee.available && fee.fee_class && (
                          <span className="ml-2 text-xs text-ep-muted font-sans">
                            ({fee.fee_class})
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>
        </div>

        {/* Facilities */}
        <Section title="Facilities" icon={<Landmark className="h-4 w-4" />}>
          <div className="flex flex-wrap gap-2.5">
            <FacilityChip
              present={facilities.wifi === 1}
              icon={<Wifi className="h-3.5 w-3.5" />}
              label="Wi-Fi campus"
            />
            <FacilityChip
              present={facilities.hostel_boys === 1}
              icon={<Users className="h-3.5 w-3.5" />}
              label="Boys hostel"
            />
            <FacilityChip
              present={facilities.hostel_girls === 1}
              icon={<Users className="h-3.5 w-3.5" />}
              label="Girls hostel"
            />
            <FacilityChip
              present={facilities.sports === 1}
              icon={<Dumbbell className="h-3.5 w-3.5" />}
              label="Sports facilities"
            />
            {facilities.campus_area_acres != null && (
              <FacilityChip
                present={true}
                icon={<Building2 className="h-3.5 w-3.5" />}
                label={`${facilities.campus_area_acres} acres`}
              />
            )}
          </div>
          {!hasFacilities && facilities.campus_area_acres == null && (
            <p className="text-sm text-ep-muted">
              Facilities data not available for this college.
            </p>
          )}
        </Section>

        {/* Gallery */}
        {profile.images.length > 1 && (
          <Section title="Gallery" icon={<Images className="h-4 w-4" />}>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {profile.images.slice(0, 9).map((img, i) => (
                <GalleryTile key={i} img={img} index={i} />
              ))}
            </div>
          </Section>
        )}

        {/* Branches */}
        <Section title="Branches offered" icon={<GraduationCap className="h-4 w-4" />}>
          {!branchesData ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : branchesData.branches.length === 0 ? (
            <NotAvailable label="Branch prediction" />
          ) : (
            <div className="overflow-x-auto -mx-5 -mb-5">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left" style={{ background: "var(--ep-bg)" }}>
                    <th
                      className="font-mono py-2.5 px-5 font-semibold text-[11px] uppercase text-ep-muted w-[42%]"
                      style={{ letterSpacing: "0.05em" }}
                    >
                      Branch
                    </th>
                    <th
                      className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-left"
                      style={{ letterSpacing: "0.05em" }}
                      title="Official CET course code"
                    >
                      Code
                    </th>
                    <th
                      className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-right"
                      style={{ letterSpacing: "0.05em" }}
                    >
                      2025 close
                    </th>
                    <th
                      className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-right"
                      style={{ letterSpacing: "0.05em" }}
                    >
                      2026 pred. close
                    </th>
                    <th
                      className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-center"
                      style={{ letterSpacing: "0.05em" }}
                    >
                      Confidence
                    </th>
                    <th
                      className="font-mono py-2.5 px-4 font-semibold text-[11px] uppercase text-ep-muted text-right"
                      style={{ letterSpacing: "0.05em" }}
                      title="General intake + TFWS intake"
                    >
                      Seats
                    </th>
                    <th className="py-2.5 px-4 w-8" />
                  </tr>
                </thead>
                <tbody>
                  {branchesData.branches.map((b) => (
                    <tr
                      key={b.canonical_code}
                      className="border-t hover:bg-[var(--ep-bg)] transition-colors"
                      style={{ borderColor: "var(--ep-border)" }}
                    >
                      <td className="py-3 px-5">
                        <Link
                          href={`/branches/${encodeURIComponent(b.canonical_code)}`}
                          className="font-semibold text-sm hover:underline"
                          style={{ color: "var(--color-ep-primary)" }}
                        >
                          {b.branch_name}
                        </Link>
                      </td>
                      <td className="py-3 px-4">
                        {b.branch_code ? (
                          <CopyableCode code={b.branch_code} />
                        ) : (
                          <span className="text-ep-muted text-xs">—</span>
                        )}
                      </td>
                      <td className="font-mono py-3 px-4 text-right text-[var(--ep-text)]">
                        {b.close_2025 != null ? fmtPercentile(b.close_2025) : "—"}
                      </td>
                      <td className="font-mono py-3 px-4 text-right text-[var(--ep-text)]">
                        {b.pred_close != null ? fmtPercentile(b.pred_close) : "—"}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {b.confidence ? (
                          <Badge variant={b.confidence as "high" | "medium" | "low"}>
                            {b.confidence}
                          </Badge>
                        ) : (
                          <span className="text-ep-muted text-xs">—</span>
                        )}
                      </td>
                      <td className="font-mono py-3 px-4 text-right text-[var(--ep-text)]">
                        {b.general_intake != null
                          ? b.tfws_intake != null
                            ? `${b.general_intake} + ${b.tfws_intake}`
                            : `${b.general_intake}`
                          : <span className="text-ep-muted text-xs">—</span>}
                      </td>
                      <td className="py-3 px-4">
                        <Link
                          href={`/branches/${encodeURIComponent(b.canonical_code)}`}
                          className="text-ep-muted hover:text-[var(--color-ep-primary)] transition-colors"
                          aria-label="View branch"
                        >
                          <TrendingUp className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {/* Contact */}
        <Section title="Contact" icon={<Phone className="h-4 w-4" />}>
          {!contact.website_url &&
          !contact.email &&
          !contact.phone &&
          !location.address ? (
            <NotAvailable label="Contact" />
          ) : (
            <div className="space-y-3">
              {location.address && (
                <div className="flex items-start gap-2 text-sm text-[var(--ep-text-secondary)]">
                  <MapPin className="h-4 w-4 shrink-0 mt-0.5 text-ep-muted" />
                  <span>{location.address}</span>
                </div>
              )}
              {contact.website_url && (
                <div className="flex items-center gap-2 text-sm">
                  <Globe className="h-4 w-4 shrink-0 text-ep-muted" />
                  <a
                    href={contact.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-ep-primary hover:underline flex items-center gap-1"
                  >
                    {contact.website_url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
              {contact.email && (
                <div className="flex items-center gap-2 text-sm text-[var(--ep-text-secondary)]">
                  <Mail className="h-4 w-4 shrink-0 text-ep-muted" />
                  <a href={`mailto:${contact.email}`} className="hover:text-ep-primary">
                    {contact.email}
                  </a>
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center gap-2 text-sm text-[var(--ep-text-secondary)]">
                  <Phone className="h-4 w-4 shrink-0 text-ep-muted" />
                  {contact.phone}
                </div>
              )}
              {location.google_maps_url && (
                <a
                  href={location.google_maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 mt-1 text-sm text-ep-primary hover:underline"
                >
                  <MapPin className="h-3.5 w-3.5" />
                  Open in Google Maps
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          )}
        </Section>
      </div>

      {/* ── Right sidebar ────────────────────────────────────────────────────── */}
      <div className="hidden lg:block">
        <Sidebar profile={profile} />
      </div>

      {/* Mobile sticky bottom bar */}
      <MobileShortlistBar profile={profile} />
    </div>
  );
}

function FacilityChip({
  present,
  icon,
  label,
}: {
  present: boolean;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 rounded-[8px] border px-[13px] py-[7px] text-sm font-medium",
        !present && "opacity-60 border-dashed"
      )}
      style={{
        background: present ? "var(--color-ep-green-tint)" : "transparent",
        borderColor: present ? "var(--color-ep-green-border)" : "var(--ep-border)",
        color: present ? "var(--ep-text-secondary)" : "var(--ep-muted)",
      }}
      title={present ? undefined : "Not available"}
    >
      <span style={{ color: present ? "var(--color-ep-green)" : "var(--ep-muted)" }}>{icon}</span>
      {label}
    </div>
  );
}

function GalleryTile({ img, index }: { img: { url: string; caption?: string | null; type?: string | null }; index: number }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="w-full rounded-[8px] overflow-hidden cursor-pointer hover:opacity-90 transition-opacity" style={{ height: 130 }}>
      {failed ? (
        <PlaceholderTile cool={index % 2 === 0} size={26} />
      ) : (
        <img
          src={googleImageUrl(img.url, "gallery")}
          alt={img.caption ?? img.type ?? `Image ${index + 1}`}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

function MobileShortlistBar({ profile }: { profile: CollegeProfile }) {
  const { toggle, isSaved } = useShortlist();
  const saved = isSaved(profile.college_code);

  return (
    <div
      className="lg:hidden fixed bottom-0 left-0 right-0 z-20 border-t border-[var(--ep-border)] px-5 py-3 flex gap-3"
      style={{ background: "var(--ep-surface)" }}
    >
      <button
        onClick={() =>
          toggle({
            code: profile.college_code,
            name: profile.college_name,
            city: profile.location.district,
            score: profile.score.overall,
            institution_type: profile.identity.institution_type,
            imageUrl: profile.images[0]?.url ?? null,
          })
        }
        className={cn(
          "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-[10px] text-sm font-medium transition-all border",
          saved
            ? "border-[var(--color-ep-primary)] text-[var(--color-ep-primary)]"
            : "border-[var(--ep-border)] text-[var(--ep-text-secondary)] hover:border-[var(--color-ep-primary)] hover:text-[var(--color-ep-primary)]"
        )}
        style={saved ? { background: "rgba(198,82,47,0.08)" } : { background: "var(--ep-surface)" }}
      >
        {saved ? (
          <Check className="h-4 w-4" />
        ) : (
          <Bookmark className="h-4 w-4" fill="none" stroke="currentColor" />
        )}
        {saved ? "Saved" : "Save"}
      </button>
      <Link
        href="/my-shortlist"
        className="px-4 py-2.5 rounded-[10px] border border-[var(--ep-border)] text-sm text-[var(--ep-text-secondary)] hover:bg-[var(--ep-bg)] transition-colors"
      >
        Bookmarks
      </Link>
    </div>
  );
}

// ── Page shell ────────────────────────────────────────────────────────────────

export default function CollegePage() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();

  const {
    data: profile,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["college", code],
    queryFn: () => getCollegeProfile(code),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });

  return (
    <div className="min-h-screen pb-20 lg:pb-0" style={{ background: "var(--ep-bg)" }}>
      <NavHeader
        right={
          profile ? (
            <div className="flex items-center gap-2 text-xs text-ep-muted">
              <GraduationCap className="h-3.5 w-3.5" />
              {profile.location.district ?? ""}
            </div>
          ) : undefined
        }
      />

      <main className="mx-auto max-w-6xl px-6 py-8">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ep-muted hover:text-[var(--ep-text)] mb-[18px] transition-colors"
        >
          <ChevronLeft className="h-[15px] w-[15px]" />
          Back to Discover
        </button>

        {isLoading && (
          <div className="space-y-6">
            <Skeleton className="h-72 w-full rounded-[13px]" />
            <Skeleton className="h-24 w-full" />
            <div className="grid grid-cols-2 gap-6">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          </div>
        )}

        {error && (
          <div
            className="rounded-[10px] border px-5 py-4 text-sm flex items-start gap-3"
            style={{ borderColor: "var(--color-ep-red-border)", background: "var(--color-ep-red-tint)", color: "var(--color-ep-red-ink)" }}
          >
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Could not load college profile</p>
              <p className="mt-0.5 opacity-80">
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
          </div>
        )}

        {profile && <CollegeProfileView profile={profile} code={code} />}
      </main>
    </div>
  );
}
