"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
 * "The Path" nav header.
 * Changes vs. the old version:
 *  - PNG logo → inline <EduPathLogo/> (bezier mark + Instrument Serif wordmark)
 *  - warm surface + hairline border come free from the updated tokens
 *  - logged-in identity chip → compact circular initials avatar
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

  // A nav item is active when the current route lives under it. Discover ("/")
  // also owns college/branch detail pages so drilling into a college keeps it lit.
  const isActive = (href: string) =>
    href === "/"
      ? pathname === "/" || pathname.startsWith("/colleges") || pathname.startsWith("/branches")
      : pathname === href || pathname.startsWith(href + "/");

  const navLink = (active: boolean) =>
    `flex items-center gap-1.5 text-[14px] font-medium px-3.5 py-1.5 rounded-full transition-colors ${
      active ? "" : "text-[var(--ep-text-secondary)] hover:text-[var(--ep-text)]"
    }`;
  const activeStyle = (active: boolean) =>
    active ? { background: "var(--color-ep-amber)", color: "#241C15" } : undefined;

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

          <nav className="hidden sm:flex items-center gap-1">
            <Link href="/" className={navLink(isActive("/"))} style={activeStyle(isActive("/"))}>
              Discover
            </Link>
            <Link
              href="/my-shortlist"
              className={navLink(isActive("/my-shortlist"))}
              style={activeStyle(isActive("/my-shortlist"))}
            >
              <Bookmark className="h-3.5 w-3.5" />
              Bookmarks
              {count > 0 && (
                <span
                  className="inline-flex items-center justify-center h-5 min-w-[1.25rem] px-1 rounded-full text-[11px] font-semibold text-white"
                  style={{ background: "var(--color-ep-primary)" }}
                >
                  {count}
                </span>
              )}
            </Link>
            <Link href="/compare" className={navLink(isActive("/compare"))} style={activeStyle(isActive("/compare"))}>
              <GitCompareArrows className="h-3.5 w-3.5" />
              Compare
              {compareCount > 0 && (
                <span
                  className="inline-flex items-center justify-center h-5 min-w-[1.25rem] px-1 rounded-full text-[11px] font-semibold text-white"
                  style={{ background: "var(--color-ep-primary)" }}
                >
                  {compareCount}
                </span>
              )}
            </Link>
            {isLoggedIn && (
              <>
                <Link href="/students" className={navLink(isActive("/students"))} style={activeStyle(isActive("/students"))}>
                  <Users className="h-3.5 w-3.5" />
                  Students
                </Link>
                <Link href="/dashboard" className={navLink(isActive("/dashboard"))} style={activeStyle(isActive("/dashboard"))}>
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
