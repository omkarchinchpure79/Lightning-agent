"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  fetchDistricts,
  fetchNaacGrades,
  fetchFilterRanges,
  fetchBranchKeywords,
  type FilterRanges,
} from "@/lib/api";

export interface SidebarFilterState {
  district?: string;
  institutionType?: string;
  naacGrade?: string;
  branch?: string;
  scoreMin?: number;
  scoreMax?: number;
  percentileMin?: number;
  percentileMax?: number;
}

interface DiscoveryFiltersProps {
  value: SidebarFilterState;
  onChange: (next: SidebarFilterState) => void;
  onClose?: () => void;
  resultCount?: number;
}

const inputStyle = { background: "var(--ep-input)", borderColor: "var(--ep-border-strong)" };

export function DiscoveryFilters({ value, onChange, onClose, resultCount }: DiscoveryFiltersProps) {
  const [districts, setDistricts] = useState<string[]>([]);
  const [naacGrades, setNaacGrades] = useState<string[]>([]);
  const [branchKeywords, setBranchKeywords] = useState<string[]>([]);
  const [ranges, setRanges] = useState<FilterRanges | null>(null);

  useEffect(() => {
    fetchDistricts().then(setDistricts).catch(() => {});
    fetchNaacGrades().then(setNaacGrades).catch(() => {});
    fetchBranchKeywords().then(setBranchKeywords).catch(() => {});
    fetchFilterRanges().then(setRanges).catch(() => {});
  }, []);

  const hasActiveFilters =
    value.district || value.institutionType || value.naacGrade || value.branch ||
    value.scoreMin != null || value.scoreMax != null ||
    value.percentileMin != null || value.percentileMax != null;

  function update(patch: Partial<SidebarFilterState>) {
    onChange({ ...value, ...patch });
  }

  function clearAll() {
    onChange({});
  }

  const scoreFloor = ranges?.score_min ?? 0;
  const scoreCeil = ranges?.score_max ?? 100;
  const pctFloor = ranges?.percentile_min ?? 0;
  const pctCeil = ranges?.percentile_max ?? 100;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg text-[var(--ep-text)]">Filters</h3>
        <div className="flex items-center gap-3">
          {hasActiveFilters && (
            <button
              onClick={clearAll}
              className="text-xs font-medium hover:underline"
              style={{ color: "var(--color-ep-primary)" }}
            >
              Clear all
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close filters"
              className="sm:hidden text-ep-muted hover:text-[var(--ep-text)]"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      {resultCount != null && (
        <p className="font-mono text-xs text-ep-muted -mt-4">{resultCount} colleges match</p>
      )}

      {/* Location / District */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          Location
        </label>
        <select
          value={value.district ?? ""}
          onChange={(e) => update({ district: e.target.value || undefined })}
          className="w-full rounded-[10px] border px-3 py-2 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
          style={inputStyle}
        >
          <option value="">All districts</option>
          {districts.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>

      {/* Government vs Private */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          Institution type
        </label>
        <div className="flex flex-col gap-1.5">
          {[
            { label: "All", value: undefined },
            { label: "Government", value: "gov" },
            { label: "Private", value: "pvt" },
          ].map((opt) => (
            <label key={opt.label} className="flex items-center gap-2 text-sm text-[var(--ep-text)] cursor-pointer">
              <input
                type="radio"
                name="institution_type"
                checked={(value.institutionType ?? undefined) === opt.value}
                onChange={() => update({ institutionType: opt.value })}
                className="accent-[var(--color-ep-primary)]"
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      {/* NAAC Grade */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          NAAC grade
        </label>
        <select
          value={value.naacGrade ?? ""}
          onChange={(e) => update({ naacGrade: e.target.value || undefined })}
          className="w-full rounded-[10px] border px-3 py-2 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
          style={inputStyle}
        >
          <option value="">Any grade</option>
          {naacGrades.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      </div>

      {/* Branch / Stream */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          Branch / Stream
        </label>
        <select
          value={value.branch ?? ""}
          onChange={(e) => update({ branch: e.target.value || undefined })}
          className="w-full rounded-[10px] border px-3 py-2 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
          style={inputStyle}
        >
          <option value="">All Branches</option>
          {branchKeywords.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </div>

      {/* Score range */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          Score range
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder={String(scoreFloor)}
            value={value.scoreMin ?? ""}
            onChange={(e) => update({ scoreMin: e.target.value ? Number(e.target.value) : undefined })}
            className="font-mono w-full rounded-[10px] border px-2 py-1.5 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
            style={inputStyle}
            min={scoreFloor}
            max={scoreCeil}
            step={0.5}
          />
          <span className="text-ep-muted text-xs">to</span>
          <input
            type="number"
            placeholder={String(scoreCeil)}
            value={value.scoreMax ?? ""}
            onChange={(e) => update({ scoreMax: e.target.value ? Number(e.target.value) : undefined })}
            className="font-mono w-full rounded-[10px] border px-2 py-1.5 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
            style={inputStyle}
            min={scoreFloor}
            max={scoreCeil}
            step={0.5}
          />
        </div>
      </div>

      {/* Percentile range — the college's toughest-branch real closing percentile */}
      <div>
        <label
          className="font-mono block text-[10px] uppercase mb-2"
          style={{ letterSpacing: "0.08em", color: "var(--color-ep-muted)" }}
        >
          Cutoff percentile
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder={pctFloor.toFixed(1)}
            value={value.percentileMin ?? ""}
            onChange={(e) => update({ percentileMin: e.target.value ? Number(e.target.value) : undefined })}
            className="font-mono w-full rounded-[10px] border px-2 py-1.5 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
            style={inputStyle}
            min={0}
            max={100}
            step={0.1}
          />
          <span className="text-ep-muted text-xs">to</span>
          <input
            type="number"
            placeholder={pctCeil.toFixed(1)}
            value={value.percentileMax ?? ""}
            onChange={(e) => update({ percentileMax: e.target.value ? Number(e.target.value) : undefined })}
            className="font-mono w-full rounded-[10px] border px-2 py-1.5 text-sm text-[var(--ep-text)] outline-none focus:border-[var(--color-ep-primary)]"
            style={inputStyle}
            min={0}
            max={100}
            step={0.1}
          />
        </div>
      </div>
    </div>
  );
}
