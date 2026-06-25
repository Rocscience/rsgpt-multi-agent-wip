import { NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/auth0'

const BASE = process.env.API_BASE_URL

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const { sessionId } = await params

    const upstream = await fetch(`${BASE}/api/v1/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })

    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: 'Failed to delete session' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (error) {
    console.error('Delete session API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Service temporarily unavailable. Please try again later.' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

