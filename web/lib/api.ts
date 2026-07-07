/**
 * Typed API client — all backend calls go through here, never raw fetch().
 * Base URL: NEXT_PUBLIC_API_URL (defaults to http://localhost:8000)
 */

import { TOKEN_KEY } from "./useAuth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error(
      "Can't connect to the prediction engine. Make sure the backend is running on port 8000."
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Server error ${res.status}`
    );
  }
  return res.json() as Promise<T>;
}

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  return request<T>(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
}

// ─── Lookup types ────────────────────────────────────────────────────────────

export type CategoryOption = { label: string; code: string; dse_supported: boolean };

export async function fetchDistricts(): Promise<string[]> {
  return request<string[]>("/api/lookups/districts");
}
export async function fetchCategories(): Promise<CategoryOption[]> {
  return request<CategoryOption[]>("/api/lookups/categories");
}
export async function fetchBranchKeywords(): Promise<string[]> {
  return request<string[]>("/api/lookups/branches");
}
export async function fetchNaacGrades(): Promise<string[]> {
  return request<string[]>("/api/lookups/naac-grades");
}
export interface SiteStats {
  college_count: number;
  district_count: number;
  cutoff_year_min: number;
  cutoff_year_max: number;
  cutoff_year_count: number;
}
export async function fetchSiteStats(): Promise<SiteStats> {
  return request<SiteStats>("/api/lookups/stats");
}
export interface FilterRanges {
  score_min: number | null;
  score_max: number | null;
  year_min: number | null;
  year_max: number | null;
  percentile_min: number | null;
  percentile_max: number | null;
}
export async function fetchFilterRanges(): Promise<FilterRanges> {
  return request<FilterRanges>("/api/lookups/filter-ranges");
}

// ─── Student types ───────────────────────────────────────────────────────────

export type AdmissionType = "fe" | "dse";

export interface StudentCreate {
  name: string;
  gender?: "M" | "F" | "Other" | null;
  // Required for fe; for dse the API mirrors diploma_pct into it.
  percentile?: number | null;
  admission_type?: AdmissionType;
  diploma_pct?: number | null;
  jee_main_rank?: number | null;
  board_pct?: number | null;
  category_base: string;
  category_variant?: string | null;
  home_district?: string | null;
  pwd_status?: boolean;
  pwd_type?: string | null;
  defense_status?: boolean;
  tfws_eligible?: boolean;
  orphan_status?: boolean;
  ews_eligible?: boolean;
  family_income_bracket?: string | null;
  preferred_branches?: string[];
  preferred_locations?: string[];
  max_fee?: number | null;
  notes?: string | null;
  counsellor_id?: string | null;
}

export type StudentUpdate = Partial<StudentCreate>;

export interface Student extends StudentCreate {
  id: number;
  percentile: number; // always set server-side (mirrors diploma_pct for dse)
  created_at: string;
  updated_at: string;
}

export interface StudentListItem {
  id: number;
  name: string;
  percentile: number;
  admission_type: AdmissionType;
  category_base: string;
  home_district: string | null;
  updated_at: string;
}

// ─── Prediction types ────────────────────────────────────────────────────────

export interface FeeInfo {
  available: boolean;
  total_annual?: number;
  fee_class?: string;
  reason?: string;
}

export interface PredictionRow {
  canonical_code: string;
  entry_key: string;
  college_code: string;
  college_name: string;
  branch_name: string;
  branch_code: string | null;
  general_intake: number | null;
  tfws_intake: number | null;
  city: string;
  college_score: number | null;
  seat_type: string;
  category_used: string;
  predicted_close: number;
  predicted_low: number | null;
  predicted_high: number | null;
  margin: number;
  band: "SAFE" | "PROBABLE" | "REACH";
  confidence: "high" | "medium" | "low";
  trend_slope: number | null;
  years_used: number;
  fee: FeeInfo;
  within_budget: boolean | null;
  seat_data_status?: "exact" | "fallback" | "state_only";
  expected_category?: string;
  seat_pool?: "TFWS" | "Defence" | "Orphan" | "PwD" | "EWS" | null;
}

export interface PredictionResult {
  admission_type?: AdmissionType; // "dse" when built from the DSE data plane
  percentile: number;             // for dse this is the diploma percentage
  base_category: string;
  home_district: string | null;
  resolved_district: string | null;
  student_university: string | null;
  student_university_name: string | null;
  round_num: number;
  branch_preferences: string[] | null;
  fee_budget: number | null;
  counts: {
    safe: number;
    probable: number;
    reach: number;
    over_budget_hidden: number;
    fee_unknown_kept: number;
  };
  district_unresolved: boolean;
  safe: PredictionRow[];
  probable: PredictionRow[];
  reach: PredictionRow[];
}

export interface ShortlistItem {
  canonical_code: string;
  college_name?: string | null;
  branch_name?: string | null;
  band?: string | null;
  predicted_close?: number | null;
  margin?: number | null;
  confidence?: string | null;
  category_used?: string | null;
  seat_type?: string | null;
  fee_text?: string | null;
  branch_code?: string | null;
  college_score?: number | null;
  seat_pool?: string | null;
}

export interface ShortlistResponse {
  student_id: number;
  items: ShortlistItem[];
}

// ─── API calls ───────────────────────────────────────────────────────────────

export async function createStudent(data: StudentCreate): Promise<Student> {
  return authRequest<Student>("/api/students", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getStudent(id: number): Promise<Student> {
  return authRequest<Student>(`/api/students/${id}`);
}

export async function updateStudent(id: number, data: StudentUpdate): Promise<Student> {
  return authRequest<Student>(`/api/students/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function listStudents(): Promise<StudentListItem[]> {
  return authRequest<StudentListItem[]>("/api/students");
}

export async function deleteStudent(id: number): Promise<void> {
  await authRequest<void>(`/api/students/${id}`, { method: "DELETE" });
}

export async function getStudentPredictions(
  id: number,
  roundNum = 1
): Promise<PredictionResult> {
  return authRequest<PredictionResult>(`/api/students/${id}/predictions`, {
    method: "POST",
    body: JSON.stringify({ round_num: roundNum }),
  });
}

export async function getShortlist(studentId: number): Promise<ShortlistResponse> {
  return authRequest<ShortlistResponse>(`/api/students/${studentId}/shortlist`);
}

export async function saveShortlist(
  studentId: number,
  items: ShortlistItem[]
): Promise<ShortlistResponse> {
  return authRequest<ShortlistResponse>(`/api/students/${studentId}/shortlist`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

// ─── College types ────────────────────────────────────────────────────────────

export interface CollegeSearchResult {
  college_code: string;
  college_name: string;
  city: string | null;
  score: number | null;
  top_percentile: number | null;
  district: string | null;
  institution_type: string | null;
  naac_grade: string | null;
  thumbnail_url: string | null;
}

export interface CollegeImage {
  url: string;
  type?: "building" | "campus" | "logo" | "infrastructure" | "aerial" | string;
  caption?: string | null;
  source?: string | null;
}

export interface CollegeFeeEntry {
  available: boolean;
  total_annual?: number | null;
  fee_class?: string | null;
  reason?: string | null;
}

export interface CollegeProfile {
  college_code: string;
  paired_codes: string[];
  college_name: string;
  identity: {
    institution_type: string | null;
    management_name: string | null;
    year_established: number | null;
    is_autonomous: number | null;
  };
  accreditation: {
    naac_grade: string | null;
    naac_score: number | null;
    nirf_rank: number | null;
    nba_branches: string | null;
  };
  location: {
    district: string | null;
    university_code: string | null;
    affiliated_university: string | null;
    address: string | null;
    latitude: number | null;
    longitude: number | null;
    google_maps_url: string | null;
  };
  contact: {
    website_url: string | null;
    email: string | null;
    phone: string | null;
  };
  facilities: {
    hostel_boys: number | null;
    hostel_girls: number | null;
    sports: number | null;
    wifi: number | null;
    campus_area_acres: number | null;
  };
  placements: {
    placement_pct: number | null;
    avg_package_lpa: number | null;
    highest_package_lpa: number | null;
    top_recruiters: string | null;
    reliable: boolean;
  };
  fees: {
    GOPEN: CollegeFeeEntry;
    GOBC: CollegeFeeEntry;
    GSC: CollegeFeeEntry;
    TFWS: CollegeFeeEntry;
  };
  score: {
    overall: number | null;
    completeness: number | null;
    subsets: Record<string, number>;
  };
  images: CollegeImage[];
  image_count: number;
  cutoff_trends: Array<{
    branch_name: string;
    close_2023: number | null;
    close_2024: number | null;
    close_2025: number | null;
    pred_2026: number | null;
  }>;
  dse_cutoff_trends: Array<{
    branch_name: string;
    canonical_code: string | null;
    close_2023: number | null;
    close_2024: number | null;
    close_2025: number | null;
    pred_next: number | null;
  }>;
  image_warning: string;
}

export interface CollegeBranch {
  canonical_code: string;
  branch_name: string;
  branch_code: string | null;
  pred_close: number | null;
  confidence: string | null;
  years_used: number | null;
  close_2025: number | null;
  general_intake: number | null;
  tfws_intake: number | null;
}

export interface CollegeBranchesResponse {
  college_code: string;
  college_name: string;
  branches: CollegeBranch[];
}

export interface HistoricalCutoff {
  year: number;
  round: number;
  category: string;
  percentile: number;
}

export interface Prediction2026 {
  round: number;
  category: string;
  predicted_pct: number;
  predicted_low: number | null;
  predicted_high: number | null;
  confidence: string;
  trend_slope: number | null;
  years_used: number;
}

export interface BranchDeepDive {
  canonical_code: string;
  college_code: string;
  college_name: string;
  branch_name: string;
  branch_codes: string[];
  general_intake: number | null;
  tfws_intake: number | null;
  cutoff_trends: HistoricalCutoff[];
  predictions_2026: Prediction2026[];
}

// ─── College + branch API calls ───────────────────────────────────────────────

export type CollegeSortBy = "score" | "percentile";

export interface CollegeSearchFilters {
  q?: string;
  district?: string;
  institutionType?: string;
  naacAboveA?: boolean;
  naacGrade?: string;
  yearMin?: number;
  yearMax?: number;
  scoreMin?: number;
  scoreMax?: number;
  percentileMin?: number;
  percentileMax?: number;
  branch?: string;
  sortBy?: CollegeSortBy;
}

export async function searchColleges(
  q = "",
  district?: string,
  institutionType?: string,
  limit = 20,
  offset = 0,
  naacAboveA = false,
  extra?: Omit<CollegeSearchFilters, "q" | "district" | "institutionType" | "naacAboveA">,
): Promise<CollegeSearchResult[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (district) params.set("district", district);
  if (institutionType) params.set("institution_type", institutionType);
  if (naacAboveA) params.set("naac_above_a", "true");
  if (extra?.naacGrade) params.set("naac_grade", extra.naacGrade);
  if (extra?.yearMin != null) params.set("year_min", String(extra.yearMin));
  if (extra?.yearMax != null) params.set("year_max", String(extra.yearMax));
  if (extra?.scoreMin != null) params.set("score_min", String(extra.scoreMin));
  if (extra?.scoreMax != null) params.set("score_max", String(extra.scoreMax));
  if (extra?.percentileMin != null) params.set("percentile_min", String(extra.percentileMin));
  if (extra?.percentileMax != null) params.set("percentile_max", String(extra.percentileMax));
  if (extra?.branch) params.set("branch", extra.branch);
  if (extra?.sortBy) params.set("sort_by", extra.sortBy);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request<CollegeSearchResult[]>(`/api/colleges/search?${params}`);
}

export async function getCollegeProfile(code: string): Promise<CollegeProfile> {
  return request<CollegeProfile>(`/api/colleges/${encodeURIComponent(code)}`);
}

export async function getCollegeBranches(code: string): Promise<CollegeBranchesResponse> {
  return request<CollegeBranchesResponse>(`/api/colleges/${encodeURIComponent(code)}/branches`);
}

export async function getBranchDeepDive(canonicalCode: string): Promise<BranchDeepDive> {
  return request<BranchDeepDive>(`/api/branches/${encodeURIComponent(canonicalCode)}`);
}

export interface DseBranchDeepDive {
  canonical_code: string;
  college_code: string;
  college_name: string;
  branch_name: string;
  choice_codes: string[];
  cutoff_trends: HistoricalCutoff[];
  predictions_2026: Prediction2026[];
}

export async function getDseBranchDeepDive(canonicalCode: string): Promise<DseBranchDeepDive> {
  return request<DseBranchDeepDive>(`/api/dse-branches/${encodeURIComponent(canonicalCode)}`);
}

// ─── AI College description ───────────────────────────────────────────────────

export interface CollegeDescription {
  college_code: string;
  description: string;
  generated_at: string;
  edited_by_counselor: boolean;
  from_cache: boolean;
}

export async function getCollegeDescription(code: string): Promise<CollegeDescription> {
  return request<CollegeDescription>(`/api/colleges/${encodeURIComponent(code)}/description`);
}

export async function generateCollegeDescription(
  code: string,
  force = false
): Promise<CollegeDescription> {
  return request<CollegeDescription>(
    `/api/colleges/${encodeURIComponent(code)}/generate-description${force ? "?force=true" : ""}`,
    { method: "POST" }
  );
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  counselor_id: number;
  name: string;
  email: string;
}

export async function authSignup(
  name: string,
  email: string,
  password: string
): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });
}

export async function authLogin(
  email: string,
  password: string
): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// ─── Counselor shortlist ──────────────────────────────────────────────────────

export interface CounselorShortlistItem {
  college_code: string;
  college_name: string | null;
  city: string | null;
  score: number | null;
  institution_type: string | null;
  saved_at: string;
}

export interface CounselorShortlistIn {
  college_code: string;
  college_name?: string | null;
  city?: string | null;
  score?: number | null;
  institution_type?: string | null;
}

export async function getCounselorShortlist(): Promise<CounselorShortlistItem[]> {
  return authRequest<CounselorShortlistItem[]>("/api/me/shortlist");
}

export async function addCollegeToShortlist(
  college: CounselorShortlistIn
): Promise<CounselorShortlistItem> {
  return authRequest<CounselorShortlistItem>("/api/me/shortlist", {
    method: "POST",
    body: JSON.stringify(college),
  });
}

export async function removeCollegeFromShortlist(code: string): Promise<void> {
  await authRequest<void>(`/api/me/shortlist/${encodeURIComponent(code)}`, {
    method: "DELETE",
  });
}

export async function bulkAddToShortlist(
  items: CounselorShortlistIn[]
): Promise<void> {
  await authRequest<void>("/api/me/shortlist/bulk", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}
