import { NextRequest, NextResponse } from "next/server";

/**
 * UX-level route gating only — real authorization happens in the Django API.
 * `cs_session` is a non-sensitive marker cookie set alongside the HttpOnly
 * auth cookies; its presence means "probably signed in".
 */
export function middleware(request: NextRequest) {
  const hasSession = request.cookies.has("cs_session");
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/app") && !hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  if ((pathname === "/login" || pathname === "/register") && hasSession) {
    return NextResponse.redirect(new URL("/app", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/login", "/register"],
};
