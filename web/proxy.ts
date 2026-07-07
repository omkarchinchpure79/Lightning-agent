import { NextRequest, NextResponse } from "next/server";

/**
 * Hard login gate — every route except /login and /signup requires the
 * edupath_token cookie (mirror of the localStorage JWT, set on login/signup
 * so middleware can see it; the API still verifies the JWT signature on
 * every request, this cookie only gates page rendering).
 */
const PUBLIC_PATHS = ["/login", "/signup"];

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
  if (isPublic) return NextResponse.next();

  const token = req.cookies.get("edupath_token")?.value;
  if (!token) {
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all routes except:
     * - _next/static, _next/image (Next internals)
     * - favicon/icon files
     */
    "/((?!_next/static|_next/image|favicon|apple-icon|logo-|.*\\.png$|.*\\.ico$).*)",
  ],
};
