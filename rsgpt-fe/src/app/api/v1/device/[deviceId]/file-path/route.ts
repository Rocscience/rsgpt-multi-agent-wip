import { getAccessToken } from "@/lib/auth0";
import { NextRequest } from "next/server";

const BASE = process.env.API_BASE_URL

/* 
Request file path selection from a device
POST /api/v1/device/[deviceId]/file-path
*/
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ deviceId: string }> }
) {
    try {
        const token = await getAccessToken()

        if (!token) {
            return new Response(JSON.stringify({ error: 'Unauthorized' }), {
                status: 401,
                headers: { 'Content-Type': 'application/json' },
            })
        }

        const deviceId = (await params).deviceId

        if (!deviceId) {
            return new Response(JSON.stringify({ error: 'Device ID is required' }), {
                status: 400,
                headers: { 'Content-Type': 'application/json' },
            })
        }

        // Get screen info from request body (optional)
        let screenInfo
        try {
            const body = await req.json()
            screenInfo = body.screenInfo
        } catch {
            // No body or invalid JSON - that's okay, screenInfo is optional
        }

        const upstream = await fetch(
            `${BASE}/api/v1/device/${deviceId}/file-path`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ screenInfo }),
                cache: 'no-store',
            }
        )

        if (!upstream.ok) {
            // Try to get the actual error message from the backend
            let errorMessage = 'Failed to request file path'
            try {
                const errorData = await upstream.json()
                errorMessage = errorData.detail || errorData.error || errorMessage
            } catch {
                // If we can't parse the error, use the default message
            }
            
            return new Response(JSON.stringify({ error: errorMessage }), {
                status: upstream.status,
                headers: { 'Content-Type': 'application/json' },
            })
        }
        
        return new Response(await upstream.text(), {
            status: upstream.status,
            headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
        })
    } catch (error) {
        console.error('File path API error:', error)
        return new Response(JSON.stringify({ error: 'Internal server error' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
        })
    }
}
