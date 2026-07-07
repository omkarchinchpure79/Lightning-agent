"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Plus, Check } from "lucide-react";

import { authSignup } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { ThemeToggle } from "@/components/ThemeToggle";
import { EduPathLogo } from "@/components/EduPathLogo";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

// ponytail: simple length/variety heuristic, not a real entropy estimator —
// upgrade to zxcvbn if password policy ever needs to be defensible.
function passwordStrength(pw: string): { score: 0 | 1 | 2 | 3; label: string } {
  if (!pw) return { score: 0, label: "" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++;
  const labels = ["Weak", "Weak", "Good", "Strong"];
  return { score: Math.min(score, 3) as 0 | 1 | 2 | 3, label: labels[score] };
}

const schema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});
type FormData = z.infer<typeof schema>;

export default function SignupPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const pwValue = watch("password") ?? "";
  const strength = useMemo(() => passwordStrength(pwValue), [pwValue]);
  const strengthColor = ["var(--ep-border-strong)", "var(--color-ep-red)", "var(--color-ep-amber)", "var(--color-ep-green)"][strength.score];

  async function onSubmit(data: FormData) {
    try {
      const res = await authSignup(data.name, data.email, data.password);
      login(res.token, { counselor_id: res.counselor_id, name: res.name, email: res.email });
      router.push("/");
    } catch (e: unknown) {
      setError("root", { message: (e as Error).message ?? "Signup failed" });
    }
  }

  // ── Signup — same trust panel as Login, but the copy speaks to a *new*
  // counselor deciding whether to bother creating an account at all: lead
  // with what they get, not "Start your path" filler.
  return (
    <div className="min-h-screen flex" style={{ background: "var(--ep-bg)" }}>
      <div
        className="hidden lg:flex lg:w-[46%] relative overflow-hidden flex-col justify-between p-12"
        style={{ background: "#0F2A21" }}
      >
        <svg
          viewBox="0 0 600 800"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full opacity-40"
          aria-hidden="true"
        >
          <path
            d="M-20 700 C 120 380, 360 260, 620 300"
            fill="none"
            stroke="#3C5A4C"
            strokeWidth="2"
            strokeDasharray="2 9"
            strokeLinecap="round"
          />
        </svg>

        <EduPathLogo size={32} />

        <div className="relative">
          <div
            className="font-mono text-xs uppercase mb-4 flex items-center gap-2"
            style={{ letterSpacing: "0.18em", color: "#8FBFA3" }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--color-ep-green)" }} />
            Free for counsellors
          </div>
          <h1 className="font-display text-[38px] leading-[1.08] mb-4" style={{ color: "#F6F1E7" }}>
            Stop guessing at<br />
            <span className="italic" style={{ color: "var(--color-ep-amber)" }}>cutoffs.</span> Start predicting.
          </h1>
          <ul className="space-y-2.5 text-[14px]" style={{ color: "#B8C7BE" }}>
            {["3 years of real CAP cutoff data", "SAFE / PROBABLE / REACH bands per branch", "Shareable preference lists per student"].map((f) => (
              <li key={f} className="flex items-center gap-2.5">
                <Check className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--color-ep-green)" }} />
                {f}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative text-[13px]" style={{ color: "#8FA895" }}>
          Already trusted by EduPath&apos;s counselling team.
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 py-16 relative">
        <div className="absolute top-6 right-6">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-[380px]">
          <div className="lg:hidden flex flex-col items-center mb-8">
            <EduPathLogo size={36} />
          </div>

          <h2 className="font-display text-2xl text-[var(--ep-text)] mb-1">Create your account</h2>
          <p className="text-sm text-ep-muted mb-7">Takes under a minute.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" type="text" autoComplete="name" {...register("name")} placeholder="Priya Deshmukh" />
              {errors.name && <p className="text-xs text-[var(--color-ep-red)]">{errors.name.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" {...register("email")} placeholder="you@example.com" />
              {errors.email && <p className="text-xs text-[var(--color-ep-red)]">{errors.email.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="new-password"
                  {...register("password")}
                  placeholder="Min. 8 characters"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ep-muted hover:text-[var(--ep-text)]"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {pwValue.length > 0 && (
                <div className="flex items-center gap-2 pt-0.5">
                  <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: "var(--ep-border)" }}>
                    <div
                      className="h-full rounded-full transition-all duration-200"
                      style={{ width: `${(strength.score / 3) * 100}%`, background: strengthColor }}
                    />
                  </div>
                  <span className="text-[11px] font-medium" style={{ color: strengthColor }}>{strength.label}</span>
                </div>
              )}
              {errors.password && <p className="text-xs text-[var(--color-ep-red)]">{errors.password.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                {...register("confirmPassword")}
                placeholder="••••••••"
              />
              {errors.confirmPassword && (
                <p className="text-xs text-[var(--color-ep-red)]">{errors.confirmPassword.message}</p>
              )}
            </div>

            {errors.root && (
              <p className="text-xs rounded-[8px] px-3 py-2" style={{ color: "var(--color-ep-red-ink)", background: "#F8E1DF" }}>
                {errors.root.message}
              </p>
            )}

            <Button type="submit" disabled={isSubmitting} className="w-full mt-1">
              {isSubmitting ? "Creating account…" : "Create account"}
              <Plus className="h-4 w-4" />
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ep-muted">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold hover:underline" style={{ color: "var(--color-ep-primary)" }}>
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
