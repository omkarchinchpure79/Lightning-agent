"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  Plus,
  Search,
  ChevronRight,
  Pencil,
  Trash2,
  ListChecks,
} from "lucide-react";

import { useAuth } from "@/lib/useAuth";
import { NavHeader } from "@/components/NavHeader";
import { listStudents, deleteStudent, type StudentListItem } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

type SortKey = "updated" | "name" | "percentile";

export default function StudentsPage() {
  const { isLoggedIn, loading: authLoading } = useAuth();
  const router = useRouter();

  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("updated");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  useEffect(() => {
    if (!authLoading && !isLoggedIn) router.replace("/login");
  }, [authLoading, isLoggedIn, router]);

  useEffect(() => {
    if (authLoading || !isLoggedIn) return;
    listStudents()
      .then(setStudents)
      .catch(() => setStudents([]))
      .finally(() => setLoading(false));
  }, [authLoading, isLoggedIn]);

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await deleteStudent(id);
      setStudents((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // leave list as-is; the row's delete button remains clickable to retry
    } finally {
      setDeletingId(null);
      setConfirmId(null);
    }
  }

  const filtered = useMemo(() => {
    let result = students;
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(needle) ||
          s.category_base.toLowerCase().includes(needle) ||
          (s.home_district ?? "").toLowerCase().includes(needle)
      );
    }
    const sorted = [...result];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "percentile") sorted.sort((a, b) => b.percentile - a.percentile);
    else sorted.sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
    return sorted;
  }, [students, q, sort]);

  if (authLoading || !isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--ep-bg)" }}>
        <div className="h-8 w-8 rounded-full border-2 border-[var(--color-ep-primary)] border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--ep-bg)" }}>
      <NavHeader />

      <main className="mx-auto max-w-4xl px-6 py-10 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="font-display text-[28px] text-[var(--ep-text)] flex items-center gap-2.5">
              <Users className="h-5 w-5" style={{ color: "var(--color-ep-primary)" }} />
              Students
            </h1>
            <p className="mt-1 text-sm text-ep-muted">
              {loading ? "Loading…" : `${students.length} student${students.length !== 1 ? "s" : ""} in your caseload`}
            </p>
          </div>
          <Link
            href="/students/new"
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-[10px] text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "var(--color-ep-primary)" }}
          >
            <Plus className="h-4 w-4" />
            New student
          </Link>
        </div>

        {/* Search + sort */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div
            className="flex-1 flex items-center gap-2 rounded-[10px] border px-3 py-2.5"
            style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
          >
            <Search className="h-4 w-4 text-ep-muted shrink-0" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name, category, or district..."
              className="bg-transparent text-sm text-[var(--ep-text)] outline-none placeholder:text-ep-muted w-full"
            />
          </div>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-[10px] border px-3 py-2.5 text-sm text-[var(--ep-text)] outline-none"
            style={{ background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" }}
          >
            <option value="updated">Recently updated</option>
            <option value="name">Name (A-Z)</option>
            <option value="percentile">Percentile (high to low)</option>
          </select>
        </div>

        {/* List */}
        {loading ? (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-[12px]" />
            ))}
          </div>
        ) : students.length === 0 ? (
          <div
            className="rounded-[12px] border border-dashed flex flex-col items-center gap-3 py-16"
            style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border-strong)" }}
          >
            <Users className="h-10 w-10 opacity-15 text-[var(--ep-text)]" />
            <p className="text-sm text-ep-muted">No students yet</p>
            <Link
              href="/students/new"
              className="text-sm font-medium hover:underline"
              style={{ color: "var(--color-ep-primary)" }}
            >
              Create your first student profile →
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-ep-muted">
            <p className="text-sm">No students matched &quot;{q}&quot;.</p>
          </div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {filtered.map((s, i) => (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="flex items-center gap-4 rounded-[12px] border px-5 py-3.5 hover:shadow-sm transition-shadow"
                  style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
                >
                  <div
                    className="h-10 w-10 rounded-full flex items-center justify-center shrink-0 font-display text-[15px]"
                    style={{ background: "#EDEAE1", color: "var(--color-ep-primary)" }}
                  >
                    {s.name.charAt(0).toUpperCase()}
                  </div>

                  <Link href={`/students/${s.id}/results`} className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--ep-text)] line-clamp-1">{s.name}</p>
                    <p className="font-mono mt-0.5 text-xs text-ep-muted">
                      {s.admission_type === "dse"
                        ? `${s.percentile}% diploma · DSE`
                        : `${s.percentile}%ile`}
                      {" · "}{s.category_base}
                      {s.home_district ? ` · ${s.home_district}` : ""}
                    </p>
                  </Link>

                  <div className="font-mono hidden sm:block text-xs text-ep-muted shrink-0">
                    Updated {new Date(s.updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Link
                      href={`/students/${s.id}/results`}
                      title="View predictions"
                      className="p-1.5 rounded-[6px] text-ep-muted hover:text-[var(--color-ep-primary)] hover:bg-[var(--ep-bg)] transition-colors"
                    >
                      <ListChecks className="h-4 w-4" />
                    </Link>
                    <Link
                      href={`/students/${s.id}/edit`}
                      title="Edit profile"
                      className="p-1.5 rounded-[6px] text-ep-muted hover:text-[var(--color-ep-primary)] hover:bg-[var(--ep-bg)] transition-colors"
                    >
                      <Pencil className="h-4 w-4" />
                    </Link>

                    {confirmId === s.id ? (
                      <div className="flex items-center gap-1.5 pl-1">
                        <button
                          onClick={() => handleDelete(s.id)}
                          disabled={deletingId === s.id}
                          className="text-xs font-semibold hover:underline disabled:opacity-50"
                          style={{ color: "var(--color-ep-red)" }}
                        >
                          {deletingId === s.id ? "Deleting…" : "Confirm"}
                        </button>
                        <button
                          onClick={() => setConfirmId(null)}
                          className="text-xs text-ep-muted hover:underline"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmId(s.id)}
                        title="Delete profile"
                        className="p-1.5 rounded-[6px] text-ep-muted hover:text-[var(--color-ep-red)] transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}

                    <ChevronRight className="h-4 w-4 ml-1" style={{ color: "#C4BCA9" }} />
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>
    </div>
  );
}
