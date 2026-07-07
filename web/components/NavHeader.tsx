"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { Bookmark, LogIn, LogOut, LayoutDashboard, User, Users, GitCompareArrows } from "lucide-react";
import { CollegeSearch } from "./CollegeSearch";
import { ThemeToggle } from "./ThemeToggle";
import { EduPathLogo } from "./EduPathLogo";
import { useShortlist } from "@/lib/useShortlist";
import { useCompare } from "@/lib/useCompare";
import { useAuth } from "@/lib/useAuth";

interface NavHeaderProps {
  right?: React.ReactNode;
}

/**
 * Main nav header — pill shell, brand mark, section links, quick search,
 * theme toggle, and the logged-in identity chip.
 */
export function NavHeader({ right }: NavHeaderProps) {
  const { count } = useShortlist();
  const { count: compareCount } = useCompare();
  const { counselor, isLoggedIn, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

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

  const navLink = (active: boolean) =>
    `flex items-center gap-1.5 text-[14px] font-medium px-3.5 py-1.5 rounded-full transition-colors ${
      active ? "text-white" : "text-[var(--ep-text-secondary)] hover:text-[var(--ep-text)]"
    }`;
  const navStyle = (active: boolean) => (active ? { background: "var(--color-ep-primary)" } : undefined);

  const isDiscover = pathname === "/";
  const isBookmarks = pathname === "/my-shortlist";
  const isCompare = pathname === "/compare";
  const isStudents = pathname?.startsWith("/students") ?? false;
  const isDashboard = pathname === "/dashboard";

  return (
    <div className="sticky top-4 z-20 px-4">
      <header
        className="mx-auto flex max-w-7xl items-center justify-between gap-4 rounded-full border px-5 py-2.5 shadow-[0_8px_24px_-12px_rgba(36,28,21,0.18)]"
        style={{ background: "var(--ep-surface)", borderColor: "var(--ep-border)" }}
      >
        <div className="flex items-center gap-6 min-w-0">
          <Link href="/" aria-label="EduPath home" className="shrink-0 flex items-center">
            <EduPathLogo size={26} />
          </Link>

          <nav className="hidden lg:flex items-center gap-1">
            <Link href="/" className={navLink(isDiscover)} style={navStyle(isDiscover)}>
              Discover
            </Link>
            <Link href="/my-shortlist" className={navLink(isBookmarks)} style={navStyle(isBookmarks)}>
              <Bookmark className="h-3.5 w-3.5" />
              Bookmarks
              {count > 0 && (
                <span
                  className="inline-flex items-center justify-center h-5 min-w-[1.25rem] px-1 rounded-full text-[11px] font-semibold"
                  style={
                    isBookmarks
                      ? { background: "#FFFFFF", color: "var(--color-ep-primary)" }
                      : { background: "var(--color-ep-primary)", color: "#FFFFFF" }
                  }
                >
                  {count}
                </span>
              )}
            </Link>
            <Link href="/compare" className={navLink(isCompare)} style={navStyle(isCompare)}>
              <GitCompareArrows className="h-3.5 w-3.5" />
              Compare
              {compareCount > 0 && (
                <span
                  className="inline-flex items-center justify-center h-5 min-w-[1.25rem] px-1 rounded-full text-[11px] font-semibold"
                  style={
                    isCompare
                      ? { background: "#FFFFFF", color: "var(--color-ep-primary)" }
                      : { background: "var(--color-ep-primary)", color: "#FFFFFF" }
                  }
                >
                  {compareCount}
                </span>
              )}
            </Link>
            {isLoggedIn && (
              <>
                <Link href="/students" className={navLink(isStudents)} style={navStyle(isStudents)}>
                  <Users className="h-3.5 w-3.5" />
                  Students
                </Link>
                <Link href="/dashboard" className={navLink(isDashboard)} style={navStyle(isDashboard)}>
                  <LayoutDashboard className="h-3.5 w-3.5" />
                  Dashboard
                </Link>
              </>
            )}
          </nav>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden md:block">
            <CollegeSearch />
          </div>
          {right}
          <ThemeToggle />
          {isLoggedIn ? (
            <div className="flex items-center gap-2">
              <span
                title={counselor?.name}
                className="flex items-center justify-center h-8 w-8 rounded-full text-[11px] font-semibold text-white"
                style={{ background: "var(--color-ep-primary)" }}
              >
                {initials || <User className="h-3.5 w-3.5" />}
              </span>
              <button
                onClick={handleLogout}
                title="Log out"
                className="flex items-center gap-1.5 text-[13px] font-semibold text-[var(--ep-text-secondary)] hover:text-[var(--color-ep-primary)] transition-colors px-1.5"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-1.5 text-[13px] font-semibold text-white px-3.5 py-1.5 rounded-full transition-opacity hover:opacity-90"
              style={{ background: "var(--color-ep-primary)" }}
            >
              <LogIn className="h-3.5 w-3.5" />
              Log in
            </Link>
          )}
        </div>
      </header>
    </div>
  );
}
