import { NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/auth0'

const BASE = process.env.API_BASE_URL

export async function GET(req: NextRequest) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const url = new URL(req.url)
    const qs = url.search // forwards ?page=...&page_size=...

    const upstream = await fetch(`${BASE}/api/v1/chat/sessions${qs}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })

    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: 'Failed to fetch sessions' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (error) {
    console.error('Chat sessions API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Service temporarily unavailable. Please try again later.' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

export async function POST(req: NextRequest) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    
    // Forward the request body to upstream
    const body = await req.text()

    const upstream = await fetch(`${BASE}/api/v1/chat/sessions`, {
      method: 'POST',
      headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: body,
      cache: 'no-store',
      credentials: 'include',
    })

    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: 'Failed to create session' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (error) {
    console.error('Create session API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Service temporarily unavailable. Please try again later.' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
