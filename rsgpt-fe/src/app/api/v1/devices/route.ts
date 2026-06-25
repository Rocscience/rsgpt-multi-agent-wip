import { getAccessToken } from "@/lib/auth0";

const BASE = process.env.API_BASE_URL

/* 
Get devices for an authenticated user
GET /api/v1/device/
*/
export async function GET() {
    try {
        const token = await getAccessToken()

        if (!token) {
            return new Response(JSON.stringify({ error: 'Unauthorized' }), {
                status: 401,
                headers: { 'Content-Type': 'application/json' },
            })
        }

        const upstream = await fetch(`${BASE}/api/v1/device/?include_inactive=true`, {
            method: 'GET',
            headers: { Authorization: `Bearer ${token}` },
            cache: 'no-store',
            credentials: 'include',
        })

        if (!upstream.ok) {
            return new Response(JSON.stringify({ error: 'Failed to get devices' }), {
                status: upstream.status,
                headers: { 'Content-Type': 'application/json' },
            })
        }
        
        return new Response(await upstream.text(), {
            status: upstream.status,
            headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
        })
    } catch (error) {
        console.error('Devices API error:', error);
        return new Response(JSON.stringify({ error: 'Internal server error' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
        })
    }
}
