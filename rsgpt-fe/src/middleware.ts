import { NextRequest, NextResponse } from "next/server";

import { auth0, getAccessTokenFromMiddleware } from "@/lib/auth0";
import { GetRocPortalStatusResponse } from "@/lib/types";

async function checkAndUpdateRocPortalAccess(request: NextRequest, authRes: NextResponse, session: any) {
  try {
    // Use getAccessToken which auto-refreshes expired tokens
    const accessToken = await getAccessTokenFromMiddleware(request, authRes);

    if (!accessToken) {
      // Token refresh failed - user needs to re-authenticate
      return { hasAccess: false, needsReauth: true };
    }

    // Call external API directly (can't call internal API routes from middleware)
    const response = await fetch(`${process.env.API_BASE_URL}/api/v1/user/rocportal-status`, {
      headers: { 
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      // API error - don't update session (might be transient), use cached value or false
      console.error('Error checking rocPortal access:', response.statusText);
      const cachedAccess = session?.user?.rocPortalAccess ?? false;
      return { hasAccess: cachedAccess, needsReauth: false };
    }

    const rocPortalAccess = await response.json() as GetRocPortalStatusResponse;

    // Update the session with rocPortal access status
    await auth0.updateSession(request, authRes, {
      ...session,
      user: {
        ...session.user,
        rocPortalAccess: rocPortalAccess.rocportal_status
      }
    });

    return { hasAccess: rocPortalAccess.rocportal_status, needsReauth: false };
  } catch (error) {
    // Network/other error - don't update session (might be transient), use cached value or false
    console.error('Error checking rocPortal access:', error);
    const cachedAccess = session?.user?.rocPortalAccess ?? false;
    return { hasAccess: cachedAccess, needsReauth: false };
  }
}

function hasExpiredSession(request: NextRequest): boolean {
  // Check if Auth0 session cookies exist but session is null
  // This indicates an expired session rather than no session at all
  const cookies = request.cookies;
  
  // Auth0 typically uses these cookie names (may vary based on configuration)
  const auth0Cookies = [
    'appSession',
    'appSession.0',
    'appSession.1'
  ];
  
  return auth0Cookies.some(cookieName => cookies.has(cookieName));
}

export async function middleware(request: NextRequest) {
  // Maintenance mode check - redirect all traffic to /maintenance except the maintenance page itself
  const isMaintenanceMode = process.env.NEXT_PUBLIC_MAINTENANCE === "1";
  if (isMaintenanceMode && !request.nextUrl.pathname.startsWith("/maintenance")) {
    return NextResponse.rewrite(new URL("/maintenance", request.url));
  }

  const authRes = await auth0.middleware(request);

  // Always allow auth routes and API routes to pass through
  if (request.nextUrl.pathname.startsWith("/auth") || request.nextUrl.pathname.startsWith("/api")) {
    return authRes;
  }

  const session = await auth0.getSession(request);

  // For the main page ("/"), allow unauthenticated users but check rocPortal for authenticated users
  if (request.nextUrl.pathname == "/") {
    if (!session) {
      // Check if this is an expired session
      if (hasExpiredSession(request)) {
        return NextResponse.redirect(
          new URL("/auth/logout", request.nextUrl.origin)
        );
      }
      // No session, allow access to show login buttons
      return authRes;
    }

    // User is authenticated, check/set rocPortal access (this also refreshes access token)
    const { needsReauth } = await checkAndUpdateRocPortalAccess(request, authRes, session);
    
    if (needsReauth) {
      // Refresh token expired - user needs to re-authenticate
      return NextResponse.redirect(
        new URL("/auth/logout", request.nextUrl.origin)
      );
    }
    
    return authRes;
  }

  // For all other routes, require authentication
  if (!session) {
    // Check if this is an expired session
    if (hasExpiredSession(request)) {
      return NextResponse.redirect(
        new URL("/auth/logout", request.nextUrl.origin)
      );
    }
    // user is not authenticated, redirect to login page
    return NextResponse.redirect(
      new URL("/", request.nextUrl.origin)
    );
  }

  // Check rocPortal access for protected routes (this also refreshes access token)
  const { hasAccess, needsReauth } = await checkAndUpdateRocPortalAccess(request, authRes, session);

  if (needsReauth) {
    // Refresh token expired - user needs to re-authenticate
    return NextResponse.redirect(
      new URL("/auth/logout", request.nextUrl.origin)
    );
  }

  if (!hasAccess) {
    // User is authenticated but doesn't have rocPortal access
    // Redirect them to the main page where they'll see the banner
    return NextResponse.redirect(
      new URL("/", request.nextUrl.origin)
    );
  }

  // User is authenticated and has rocPortal access, allow access
  return authRes;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     * - Any files with extensions (js, css, png, etc.)
     */
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*).*)"
  ]
};
