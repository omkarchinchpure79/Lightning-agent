"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Heart, LogIn, LogOut, LayoutDashboard, User } from "lucide-react";
import { CollegeSearch } from "./CollegeSearch";
import { ThemeToggle } from "./ThemeToggle";
import { EduPathLogo } from "./EduPathLogo";
import { useShortlist } from "@/lib/useShortlist";
import { useAuth } from "@/lib/useAuth";

interface NavHeaderProps {
  right?: React.ReactNode;
}

/**
 * "The Path" nav header.
 * Changes vs. the old version:
 *  - PNG logo → inline <EduPathLogo/> (bezier mark + Instrument Serif wordmark)
 *  - warm surface + hairline border come free from the updated tokens
 *  - logged-in identity chip → compact circular initials avatar
 */
export function NavHeader({ right }: NavHeaderProps) {
  const { count } = useShortlist();
  const { counselor, isLoggedIn, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/");
  }

  const initials =
    counselor?.name
      ?.split(" ")
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() ?? "";

  return (
    <header
      className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--ep-border)] px-8 py-4 gap-4"
      style={{ background: "var(--ep-bg)" }}
    >
      <div className="flex items-center gap-8 min-w-0">
        <Link href="/" aria-label="EduPath home" className="shrink-0 flex items-center">
          <EduPathLogo size={28} />
        </Link>

        <nav className="hidden sm:flex items-center gap-6">
          <Link
            href="/"
            className="text-[15px] font-medium text-[var(--ep-text-secondary)] hover:text-[var(--ep-text)] transition-colors"
          >
            Discover
          </Link>
          <Link
            href="/my-shortlist"
            className="text-[15px] font-medium text-[var(--ep-text-secondary)] hover:text-[var(--ep-text)] transition-colors flex items-center gap-1.5"
          >
            <Heart className="h-4 w-4" />
            My Shortlist
            {count > 0 && (
              <span
                className="inline-flex items-center justify-center h-5 min-w-[1.25rem] px-1 rounded-full text-[11px] font-semibold text-white"
                style={{ background: "var(--color-ep-primary)" }}
              >
                {count}
              </span>
            )}
          </Link>
          {isLoggedIn && (
            <Link
              href="/dashboard"
              className="text-[15px] font-medium text-[var(--ep-text-secondary)] hover:text-[var(--ep-text)] transition-colors flex items-center gap-1.5"
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Link>
          )}
        </nav>

        <CollegeSearch />
      </div>

      <div className="flex items-center gap-4 shrink-0">
        {right}
        <ThemeToggle />
        {isLoggedIn ? (
          <div className="flex items-center gap-2.5">
            <span
              title={counselor?.name}
              className="flex items-center justify-center h-9 w-9 rounded-full text-[12px] font-semibold text-white"
              style={{ background: "var(--color-ep-primary)" }}
            >
              {initials || <User className="h-4 w-4" />}
            </span>
            <button
              onClick={handleLogout}
              title="Log out"
              className="flex items-center gap-1.5 text-sm font-semibold text-[var(--ep-text-secondary)] hover:text-[var(--color-ep-primary)] transition-colors px-2 py-1.5"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Log out</span>
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-1.5 text-sm font-semibold text-white px-4 py-2 rounded-[10px] transition-opacity hover:opacity-90"
            style={{ background: "var(--color-ep-primary)" }}
          >
            <LogIn className="h-4 w-4" />
            Log in
          </Link>
        )}
      </div>
    </header>
  );
}
