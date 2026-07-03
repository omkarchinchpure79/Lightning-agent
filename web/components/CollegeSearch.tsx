"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { searchColleges, type CollegeSearchResult } from "@/lib/api";

export function CollegeSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CollegeSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchColleges(query);
        setResults(data);
        setOpen(data.length > 0);
      } catch {
        setResults([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function onOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, []);

  function navigate(code: string) {
    setQuery("");
    setResults([]);
    setOpen(false);
    router.push(`/colleges/${code}`);
  }

  return (
    <div ref={containerRef} className="relative w-56">
      <div
        className="flex items-center gap-2 rounded-[8px] border border-[var(--ep-border)] px-3 py-1.5"
        style={{ background: "var(--ep-input)" }}
      >
        <Search className="h-3.5 w-3.5 text-ep-muted shrink-0" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search colleges..."
          className="bg-transparent text-sm text-[var(--ep-text)] outline-none placeholder:text-ep-muted w-full"
        />
      </div>

      {(open || (loading && query.length >= 2)) && (
        <div
          className="absolute top-full left-0 mt-1 w-80 rounded-[8px] border border-[var(--ep-border)] shadow-lg z-50 overflow-y-auto max-h-72"
          style={{ background: "var(--ep-surface)" }}
        >
          {loading && (
            <p className="px-4 py-3 text-sm text-ep-muted">Searching...</p>
          )}
          {!loading &&
            results.map((r) => (
              <button
                key={r.college_code}
                onClick={() => navigate(r.college_code)}
                className="w-full text-left px-4 py-2.5 transition-colors border-b border-[var(--ep-border)] last:border-0 hover:bg-[var(--ep-bg)]"
              >
                <p className="text-sm font-semibold text-[var(--ep-text)] leading-snug">
                  {r.college_name}
                </p>
                <p className="text-xs text-ep-muted mt-0.5">
                  {[r.city, r.district].filter(Boolean).join(" · ")}
                  {r.score != null && ` · Score ${r.score}/100`}
                </p>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
