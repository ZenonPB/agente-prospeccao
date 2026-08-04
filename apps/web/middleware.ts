import { NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";
export async function middleware(request: NextRequest) {
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  });

  const { pathname } = request.nextUrl;

  // Allow public routes
  // Também permite /esqueci-senha e /resetar-senha sem autenticação
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/esqueci-senha") ||
    pathname.startsWith("/resetar-senha") ||
    pathname.startsWith("/aceitar-convite") ||
    pathname.startsWith("/api/auth")
  ) {
    if (token && pathname.startsWith("/login")) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  // Protect all other routes
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Security headers
  const response = NextResponse.next();
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");

  // Content Security Policy
  const isDev = process.env.NODE_ENV === "development";
  const nonce = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(16))));

  // A API pode viver em outro domínio (deploy separado). O connect-src precisa
  // autorizar a origem da API + o WebSocket correspondente (item 4.9).
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
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (NextAuth API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico|public).*)",
  ],
};
