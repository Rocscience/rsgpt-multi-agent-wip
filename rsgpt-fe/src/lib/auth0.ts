import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextRequest, NextResponse } from "next/server";

export const auth0 = new Auth0Client({
    authorizationParameters: {
        audience: process.env.AUTH0_AUDIENCE,
        scope: 'openid profile email offline_access',
    },
    async onCallback(error, _ctx, session) {
        // redirect the user to a custom error page
        if (error) {
            return NextResponse.redirect(
            new URL(`/error?error=${error.message}`, process.env.APP_BASE_URL));
        }

        if (!session) {
            return NextResponse.redirect(
                new URL(`/error?error=No session found`, process.env.APP_BASE_URL)
            );
        }

        return NextResponse.redirect(
            new URL("/", process.env.APP_BASE_URL)
        );
    },
    session: {
        rolling: true,
        absoluteDuration: 60 * 60 * 24 * 21, // 21 days
        inactivityDuration: 60 * 60 * 24 * 14, // 14 days
    }
});

/**
 * Get access token with automatic refresh. 
 * For use in API routes (App Router).
 * Returns null if refresh token is expired (user needs to re-login).
 */
export async function getAccessToken(): Promise<string | null> {
    try {
        const { token } = await auth0.getAccessToken();
        return token;
    } catch (error) {
        // Refresh token expired or invalid - user needs to re-authenticate
        console.error('Failed to get access token:', error);
        return null;
    }
}

/**
 * Get access token with automatic refresh.
 * For use in middleware where request/response are available.
 * Returns null if refresh token is expired (user needs to re-login).
 */
export async function getAccessTokenFromMiddleware(
    request: NextRequest, 
    response: NextResponse
): Promise<string | null> {
    try {
        const { token } = await auth0.getAccessToken(request, response);
        return token;
    } catch (error) {
        // Refresh token expired or invalid - user needs to re-authenticate
        console.error('Failed to get access token in middleware:', error);
        return null;
    }
}