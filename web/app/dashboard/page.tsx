"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Search,
  Bookmark,
  Building2,
  MapPin,
  Star,
  Trash2,
  Users,
  Plus,
  ChevronRight,
  Mail,
} from "lucide-react";

import { useAuth } from "@/lib/useAuth";
import { useShortlist } from "@/lib/useShortlist";
import { NavHeader } from "@/components/NavHeader";
import { listStudents, type StudentListItem } from "@/lib/api";

export default function DashboardPage() {
  const { counselor, isLoggedIn, loading } = useAuth();
  const { items, remove, count } = useShortlist();
  const router = useRouter();

  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(true);

  // Redirect to login if not authenticated (after auth has settled)
  useEffect(() => {
    if (!loading && !isLoggedIn) {
      router.replace("/login");
    }
  }, [loading, isLoggedIn, router]);

  useEffect(() => {
    if (loading || !isLoggedIn) return;
    listStudents()
      .then(setStudents)
      .catch(() => setStudents([]))
      .finally(() => setStudentsLoading(false));
  }, [loading, isLoggedIn]);

  if (loading || !isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--ep-bg)" }}>
        <div className="h-8 w-8 rounded-full border-2 border-[var(--color-ep-primary)] border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      <main className="mx-auto max-w-4xl px-6 py-10 space-y-10">
        {/* Welcome */}
        <section>
          <h1 className="font-display text-[32px] text-[var(--ep-text)] mb-1">
            Welcome back, {counselor?.name?.split(" ")[0]}
          </h1>
          <p className="text-sm text-ep-muted">Your EduPath counsellor dashboard</p>
        </section>

        {/* Quick stats */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Saved colleges"
            value={count}
            icon={<Bookmark className="h-[18px] w-[18px]" style={{ color: "var(--color-ep-primary)" }} />}
          />
          <StatCard
            label="Student profiles"
            value={studentsLoading ? "…" : students.length}
            icon={<Users className="h-[18px] w-[18px]" style={{ color: "var(--color-ep-primary)" }} />}
          />
          <StatCard
            label="Account"
            value={counselor?.email ?? ""}
            icon={<Mail className="h-[18px] w-[18px] text-ep-muted" />}
            small
          />
          <Link
            href="/"
            className="rounded-[12px] border border-dashed flex items-center justify-center gap-2 p-5 text-sm font-medium text-ep-muted hover:text-[var(--ep-text)] hover:border-[var(--ep-text)] transition-colors"
            style={{ borderColor: "var(--ep-border-strong)" }}
          >
            <Search className="h-4 w-4" />
            Discover colleges
          </Link>
        </section>

        {/* Student profiles */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-medium text-[var(--ep-text)]">
              Student profiles
            </h2>
            <div className="flex items-center gap-4">
              {students.length > 0 && (
                <Link href="/students" className="text-sm font-medium hover:underline" style={{ color: "var(--color-ep-primary)" }}>
                  View all →
                </Link>
              )}
              <Link
                href="/students/new"
                className="text-sm font-medium hover:underline flex items-center gap-1"
                style={{ color: "var(--color-ep-primary)" }}
              >
                + New profile
              </Link>
            </div>
          </div>

          {studentsLoading ? (
            <div className="space-y-2">
              {[...Array(2)].map((_, i) => (
                <div
                  key={i}
                  className="h-16 rounded-[12px] border animate-pulse"
                  style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
                />
              ))}
            </div>
          ) : students.length === 0 ? (
            <div
              className="rounded-[12px] border border-dashed flex flex-col items-center gap-3 py-12"
              style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border-strong)" }}
            >
              <Users className="h-10 w-10 opacity-15 text-[var(--ep-text)]" />
              <p className="text-sm text-ep-muted">No student profiles yet</p>
              <Link
                href="/students/new"
                className="text-sm font-medium hover:underline"
                style={{ color: "var(--color-ep-primary)" }}
              >
                Create a student profile →
              </Link>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {students.slice(0, 5).map((s, i) => (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link
                    href={`/students/${s.id}/results`}
                    className="flex items-center gap-[13px] rounded-[12px] border px-4 py-3 hover:shadow-sm transition-shadow"
                    style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
                  >
                    <div
                      className="h-[38px] w-[38px] rounded-full flex items-center justify-center shrink-0 font-display text-[15px]"
                      style={{ background: "var(--ep-input)", color: "var(--color-ep-primary)" }}
                    >
                      {s.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-[var(--ep-text)] line-clamp-1">
                        {s.name}
                      </p>
                      <p className="font-mono mt-0.5 text-xs text-ep-muted">
                        {s.percentile}% · {s.category_base}
                        {s.home_district ? ` · ${s.home_district}` : ""}
                      </p>
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0" style={{ color: "#98A2B3" }} />
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </section>

        {/* Saved bookmarks */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-medium text-[var(--ep-text)]">
              My bookmarks
            </h2>
            {count > 0 && (
              <Link
                href="/my-shortlist"
                className="text-sm font-medium hover:underline"
                style={{ color: "var(--color-ep-primary)" }}
              >
                Reorder & print →
              </Link>
            )}
          </div>

          {count === 0 ? (
            <div
              className="rounded-[12px] border border-dashed flex flex-col items-center gap-3 py-12"
              style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border-strong)" }}
            >
              <Building2 className="h-10 w-10 opacity-15 text-[var(--ep-text)]" />
              <p className="text-sm text-ep-muted">No colleges saved yet</p>
              <Link
                href="/"
                className="text-sm font-medium hover:underline"
                style={{ color: "var(--color-ep-primary)" }}
              >
                Browse colleges →
              </Link>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {items.map((college, i) => (
                <motion.div
                  key={college.code}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-[13px] rounded-[12px] border px-4 py-3 hover:shadow-sm transition-shadow"
                  style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
                >
                  <div
                    className="h-[9px] w-[9px] rounded-full shrink-0"
                    style={{ background: i === 0 ? "var(--color-ep-green)" : "var(--color-ep-primary)" }}
                  />
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/colleges/${college.code}`}
                      className="font-serif text-sm font-medium text-[var(--ep-text)] hover:text-[var(--color-ep-primary)] transition-colors line-clamp-1"
                    >
                      {college.name}
                    </Link>
                    <p className="mt-0.5 text-xs text-ep-muted flex items-center gap-1">
                      <MapPin className="h-3 w-3 shrink-0" />
                      {college.city || "Maharashtra"}
                    </p>
                  </div>
                  {college.score != null && (
                    <div className="hidden sm:flex items-center gap-1 shrink-0">
                      <Star className="h-3.5 w-3.5" style={{ color: "var(--color-ep-amber)", fill: "var(--color-ep-amber)" }} />
                      <span className="font-mono text-xs font-semibold text-[var(--ep-text)]">
                        {college.score}/100
                      </span>
                    </div>
                  )}
                  <button
                    onClick={() => remove(college.code)}
                    className="p-1.5 rounded-[6px] text-ep-muted hover:text-[var(--color-ep-red)] transition-colors shrink-0"
                    aria-label="Remove"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  small = false,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  small?: boolean;
}) {
  return (
    <div
      className="rounded-[12px] border p-4 flex flex-col gap-2"
      style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
    >
      {icon}
      <div className={small ? "text-[11px] text-[var(--ep-text)] font-medium truncate leading-tight" : "font-mono text-[26px] font-semibold text-[var(--ep-text)]"}>
        {value}
      </div>
      <div className="text-[11px] text-ep-muted">{label}</div>
    </div>
  );
}
