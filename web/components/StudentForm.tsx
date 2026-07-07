"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Check } from "lucide-react";

import { fetchDistricts, fetchCategories, fetchBranchKeywords, createStudent, updateStudent, type Student } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ── Zod schema ─────────────────────────────────────────────────────────────

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  gender: z.enum(["M", "F", "Other"]).optional().nullable(),
  percentile: z.number().min(0).max(100),
  jee_main_rank: z.number().int().positive().optional().nullable(),
  board_pct: z.number().min(0).max(100).optional().nullable(),
  category_base: z.string().min(1, "Category is required"),
  category_variant: z.string().optional().nullable(),
  home_district: z.string().optional().nullable(),
  pwd_status: z.boolean().optional(),
  pwd_type: z.string().optional().nullable(),
  defense_status: z.boolean().optional(),
  tfws_eligible: z.boolean().optional(),
  orphan_status: z.boolean().optional(),
  ews_eligible: z.boolean().optional(),
  family_income_bracket: z.string().optional().nullable(),
  preferred_branches: z.array(z.string()).optional(),
  preferred_locations: z.array(z.string()).optional(),
  max_fee: z.number().int().min(0).optional().nullable(),
  notes: z.string().optional().nullable(),
});

type FormValues = z.infer<typeof schema>;

// ── Helpers ─────────────────────────────────────────────────────────────────

const INCOME_BRACKETS = [
  "Below ₹1 lakh",
  "₹1–2.5 lakh",
  "₹2.5–6 lakh",
  "₹6–8 lakh",
  "Above ₹8 lakh",
];

const LOCATION_OPTIONS = [
  "Pune", "Mumbai", "Nashik", "Aurangabad", "Nagpur", "Amravati",
  "Kolhapur", "Solapur", "Latur", "Nanded",
];

function toNumber(val: string): number | null {
  const n = parseFloat(val);
  return isNaN(n) ? null : n;
}
function toInt(val: string): number | null {
  const n = parseInt(val, 10);
  return isNaN(n) ? null : n;
}

function SelectableChip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors select-none",
        selected ? "font-semibold" : "text-[var(--ep-text-secondary)]"
      )}
      style={
        selected
          ? { borderColor: "var(--color-ep-primary)", color: "var(--color-ep-primary)", background: "var(--color-ep-primary-tint)" }
          : { borderColor: "var(--ep-border-strong)" }
      }
    >
      {label}
      {selected && <Check className="h-3 w-3" />}
    </button>
  );
}

function toDefaultValues(student?: Student): Partial<FormValues> {
  if (!student) return { preferred_branches: [], preferred_locations: [] };
  return {
    name: student.name,
    gender: student.gender ?? undefined,
    percentile: student.percentile,
    jee_main_rank: student.jee_main_rank ?? null,
    board_pct: student.board_pct ?? null,
    category_base: student.category_base,
    category_variant: student.category_variant ?? null,
    home_district: student.home_district ?? null,
    pwd_status: student.pwd_status ?? false,
    pwd_type: student.pwd_type ?? null,
    defense_status: student.defense_status ?? false,
    tfws_eligible: student.tfws_eligible ?? false,
    orphan_status: student.orphan_status ?? false,
    ews_eligible: student.ews_eligible ?? false,
    family_income_bracket: student.family_income_bracket ?? null,
    preferred_branches: student.preferred_branches ?? [],
    preferred_locations: student.preferred_locations ?? [],
    max_fee: student.max_fee ?? null,
    notes: student.notes ?? null,
  };
}

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  student?: Student; // undefined = create mode
}

export function StudentForm({ student }: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const isEdit = !!student;

  const { data: districts = [], isLoading: loadingDistricts } = useQuery({
    queryKey: ["districts"],
    queryFn: fetchDistricts,
  });
  const { data: categories = [], isLoading: loadingCategories } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });
  const { data: branchKeywords = [], isLoading: loadingBranches } = useQuery({
    queryKey: ["branch-keywords"],
    queryFn: fetchBranchKeywords,
  });

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: toDefaultValues(student),
  });

  const pwdStatus = watch("pwd_status");
  const selectedBranches = watch("preferred_branches") ?? [];
  const selectedLocations = watch("preferred_locations") ?? [];

  async function onSubmit(values: FormValues) {
    setServerError(null);
    try {
      const payload = {
        ...values,
        home_district: values.home_district === "Other / Not listed" ? null : values.home_district,
        preferred_branches: values.preferred_branches ?? [],
        preferred_locations: values.preferred_locations ?? [],
      };

      let saved: Student;
      if (isEdit && student) {
        saved = await updateStudent(student.id, payload);
      } else {
        saved = await createStudent(payload as Parameters<typeof createStudent>[0]);
      }
      // Bust cached student + predictions so the results page re-runs against the
      // edited profile instead of serving the stale (5-min) cache — without this,
      // saving an edit appeared to do nothing ("one time thing"). Predictions are
      // cached per (studentId, round), so drop all rounds for this student.
      await queryClient.invalidateQueries({ queryKey: ["student", saved.id] });
      await queryClient.invalidateQueries({ queryKey: ["predictions", saved.id] });
      await queryClient.invalidateQueries({ queryKey: ["shortlist", saved.id] });
      router.push(`/students/${saved.id}/results`);
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    }
  }

  const loading = loadingDistricts || loadingCategories || loadingBranches;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {/* ── Personal ── */}
      <Card>
        <CardHeader>
          <CardTitle>Personal</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="col-span-2 space-y-1.5">
            <Label htmlFor="name">Student name</Label>
            <Input id="name" placeholder="Full name" {...register("name")} />
            {errors.name && <p className="text-xs text-ep-red">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label>Gender</Label>
            <Controller
              name="gender"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value ?? ""}
                  onValueChange={(v) => field.onChange(v || null)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select gender" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="M">Male</SelectItem>
                    <SelectItem value="F">Female</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Academic ── */}
      <Card>
        <CardHeader>
          <CardTitle>Academic scores</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="percentile">
              MHT-CET percentile <span className="text-ep-red">*</span>
            </Label>
            <Input
              id="percentile"
              type="number"
              step="0.01"
              min={0}
              max={100}
              placeholder="e.g. 87.5"
              className="font-mono font-semibold border-[1.5px] bg-white"
              style={{ borderColor: "var(--color-ep-primary)" }}
              {...register("percentile", { valueAsNumber: true })}
            />
            {errors.percentile && (
              <p className="text-xs text-ep-red">{errors.percentile.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="jee_main_rank">JEE Main rank</Label>
            <Input
              id="jee_main_rank"
              type="number"
              placeholder="Optional"
              {...register("jee_main_rank", {
                setValueAs: (v) => (v === "" ? null : parseInt(v, 10)),
              })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="board_pct">Board percentage</Label>
            <Input
              id="board_pct"
              type="number"
              step="0.01"
              placeholder="Optional, 0–100"
              {...register("board_pct", {
                setValueAs: (v) => (v === "" ? null : parseFloat(v)),
              })}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Category & Eligibility ── */}
      <Card>
        <CardHeader>
          <CardTitle>Category &amp; eligibility</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingCategories ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>
                  Category <span className="text-ep-red">*</span>
                </Label>
                <Controller
                  name="category_base"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map((c) => (
                          <SelectItem key={c.code} value={c.code}>
                            {c.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {errors.category_base && (
                  <p className="text-xs text-ep-red">{errors.category_base.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="category_variant">Category variant</Label>
                <Input
                  id="category_variant"
                  placeholder="Optional (e.g. GOPENS)"
                  {...register("category_variant")}
                />
              </div>
            </div>
          )}

          {/* Toggles */}
          <div className="grid grid-cols-2 gap-4 pt-1">
            {(
              [
                ["pwd_status", "PwD (person with disability)"],
                ["defense_status", "Defense quota"],
                ["tfws_eligible", "TFWS (tuition fee waiver)"],
                ["orphan_status", "Orphan quota"],
                ["ews_eligible", "EWS (economically weaker section)"],
              ] as const
            ).map(([name, label]) => (
              <div key={name} className="flex items-center gap-3">
                <Controller
                  name={name}
                  control={control}
                  render={({ field }) => (
                    <Switch
                      id={name}
                      checked={!!field.value}
                      onCheckedChange={field.onChange}
                    />
                  )}
                />
                <Label htmlFor={name} className="font-normal cursor-pointer">
                  {label}
                </Label>
              </div>
            ))}
          </div>

          {/* PwD type (conditional) */}
          {pwdStatus && (
            <div className="space-y-1.5">
              <Label htmlFor="pwd_type">PwD type</Label>
              <Input
                id="pwd_type"
                placeholder="e.g. Locomotor, Visual, Hearing"
                {...register("pwd_type")}
              />
            </div>
          )}

          {/* Income */}
          <div className="space-y-1.5">
            <Label>Family income bracket</Label>
            <Controller
              name="family_income_bracket"
              control={control}
              render={({ field }) => (
                <Select value={field.value ?? ""} onValueChange={(v) => field.onChange(v || null)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select bracket (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    {INCOME_BRACKETS.map((b) => (
                      <SelectItem key={b} value={b}>
                        {b}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Location ── */}
      <Card>
        <CardHeader>
          <CardTitle>Home district</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingDistricts ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <Controller
              name="home_district"
              control={control}
              render={({ field }) => (
                <Select value={field.value ?? ""} onValueChange={(v) => field.onChange(v || null)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select district" />
                  </SelectTrigger>
                  <SelectContent>
                    {districts.map((d) => (
                      <SelectItem key={d} value={d}>
                        {d}
                      </SelectItem>
                    ))}
                    <SelectItem value="Other / Not listed">Other / Not listed</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          )}
          <p className="mt-1.5 text-xs text-ep-muted">
            Select &quot;Other / Not listed&quot; for out-of-state or All-India candidates.
          </p>
        </CardContent>
      </Card>

      {/* ── Preferences ── */}
      <Card>
        <CardHeader>
          <CardTitle>Branch preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Branch keywords */}
          {loadingBranches ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="space-y-2">
              <Label className="font-normal text-xs text-ep-muted">Select all that apply</Label>
              <div className="flex flex-wrap gap-2">
                <Controller
                  name="preferred_branches"
                  control={control}
                  render={({ field }) => (
                    <>
                      {branchKeywords.map((kw) => {
                        const checked = (field.value ?? []).includes(kw);
                        return (
                          <SelectableChip
                            key={kw}
                            label={kw}
                            selected={checked}
                            onClick={() => {
                              const current = field.value ?? [];
                              field.onChange(
                                checked ? current.filter((v) => v !== kw) : [...current, kw]
                              );
                            }}
                          />
                        );
                      })}
                    </>
                  )}
                />
              </div>
              {selectedBranches.length > 0 && (
                <p className="text-xs text-ep-muted">
                  Selected: {selectedBranches.join(", ")}
                </p>
              )}
            </div>
          )}

          {/* Location preferences */}
          <div className="space-y-2">
            <Label className="font-normal text-xs text-ep-muted">Location preferences</Label>
            <div className="flex flex-wrap gap-2">
              <Controller
                name="preferred_locations"
                control={control}
                render={({ field }) => (
                  <>
                    {LOCATION_OPTIONS.map((loc) => {
                      const checked = (field.value ?? []).includes(loc);
                      return (
                        <SelectableChip
                          key={loc}
                          label={loc}
                          selected={checked}
                          onClick={() => {
                            const current = field.value ?? [];
                            field.onChange(
                              checked ? current.filter((v) => v !== loc) : [...current, loc]
                            );
                          }}
                        />
                      );
                    })}
                  </>
                )}
              />
            </div>
          </div>

          {/* Max fee */}
          <div className="space-y-1.5">
            <Label htmlFor="max_fee">Maximum annual fee (₹)</Label>
            <Input
              id="max_fee"
              type="number"
              step="1000"
              min={0}
              placeholder="0 = no limit"
              {...register("max_fee", {
                setValueAs: (v) => (v === "" || v === "0" ? null : parseInt(v, 10)),
              })}
            />
          </div>
        </CardContent>
      </Card>

      {/* ── Notes ── */}
      <Card>
        <CardHeader>
          <CardTitle>Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            placeholder="Counsellor notes about this student (optional)"
            rows={3}
            {...register("notes")}
          />
        </CardContent>
      </Card>

      {/* ── Submit ── */}
      {serverError && (
        <div
          className="rounded-[8px] border px-4 py-3 text-sm"
          style={{ borderColor: "var(--color-ep-red-border)", background: "var(--color-ep-red-tint)", color: "var(--color-ep-red-ink)" }}
        >
          {serverError}
        </div>
      )}

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={() => router.back()}>
          Cancel
        </Button>
        <Button type="submit" variant="success" disabled={isSubmitting || loading}>
          {isSubmitting
            ? "Saving…"
            : isEdit
            ? "Save changes and run predictions"
            : "Create & run predictions"}
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </form>
  );
}
