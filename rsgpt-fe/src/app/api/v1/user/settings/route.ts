import { auth0, getAccessToken } from "@/lib/auth0"
import { NextRequest } from "next/server"

const BASE = process.env.API_BASE_URL

/* 
Create or update user settings
PUT /api/v1/user/settings
*/
export async function PUT(req: NextRequest) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const body = await req.text()

    const upstream = await fetch(`${BASE}/api/v1/user/settings`, {
        method: 'PUT',
        headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        },
        body: body,
        cache: 'no-store',
        credentials: 'include',
    })

    if (!upstream.ok) {
        return new Response(JSON.stringify({ error: 'Failed to update user settings' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
        })
    }

    return new Response(await upstream.text(), {
        status: upstream.status,
        headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
        })
  } catch (error) {
    console.error('User settings API error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

/* GET user settings
GET /api/v1/user/settings
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

    const upstream = await fetch(`${BASE}/api/v1/user/settings`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
        credentials: 'include',
    })

    if (!upstream.ok) {
        return new Response(JSON.stringify({ error: 'Failed to get user settings' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
        })
    }

    return new Response(await upstream.text(), {
        status: upstream.status,
        headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })

  } catch (error) {
    console.error('User settings API error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
