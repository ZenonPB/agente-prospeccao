import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const sessionToken =
    request.cookies.get("next-auth.session-token")?.value ??
    request.cookies.get("__Secure-next-auth.session-token")?.value;

  const { pathname } = request.nextUrl;

  const publicPaths = [
    "/login",
    "/register",
    "/esqueci-senha",
    "/resetar-senha",
    "/aceitar-convite",
  ];
  const isPublic =
    publicPaths.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/api/auth");

  if (isPublic) {
    if (sessionToken && pathname.startsWith("/login")) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  if (!sessionToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico|public).*)"],
};
