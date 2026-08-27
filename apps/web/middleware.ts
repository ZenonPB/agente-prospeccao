import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

export async function middleware(request: NextRequest) {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    return NextResponse.next();
  }

  const token = request.cookies.get("next-auth.session-token")?.value
    ?? request.cookies.get("__Secure-next-auth.session-token")?.value;

  let isAuthenticated = false;
  if (token) {
    try {
      await jwtVerify(token, new TextEncoder().encode(secret));
      isAuthenticated = true;
    } catch {
      // token inválido ou expirado
    }
  }

  const { pathname } = request.nextUrl;

  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/esqueci-senha") ||
    pathname.startsWith("/resetar-senha") ||
    pathname.startsWith("/aceitar-convite") ||
    pathname.startsWith("/api/auth")
  ) {
    if (isAuthenticated && pathname.startsWith("/login")) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  if (!isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const response = NextResponse.next();
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");

  const isDev = process.env.NODE_ENV === "development";
  const nonceBytes = new Uint8Array(16);
  crypto.getRandomValues(nonceBytes);
  const nonce = btoa(String.fromCharCode(...nonceBytes));

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  let apiOrigin = "http://localhost:8000";
  let apiWsOrigin = "ws://localhost:8000";
  try {
    const parsed = new URL(apiUrl);
    apiOrigin = parsed.origin;
    apiWsOrigin = `${parsed.protocol === "https:" ? "wss" : "ws"}://${parsed.host}`;
  } catch {
    // mantém os defaults se NEXT_PUBLIC_API_URL estiver malformado
  }
  const connectSrc = ["'self'", apiOrigin, apiWsOrigin];

  if (isDev) {
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-eval' 'unsafe-inline' 'nonce-${nonce}'`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https: blob:",
      "font-src 'self' data:",
      `connect-src ${connectSrc.join(" ")}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");
    response.headers.set("Content-Security-Policy", csp);
  } else {
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline' 'nonce-${nonce}' 'strict-dynamic'`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https://tile.openstreetmap.org https: blob:",
      "font-src 'self' data:",
      `connect-src ${connectSrc.join(" ")}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");
    response.headers.set("Content-Security-Policy", csp);
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon.ico|public).*)",
  ],
};
