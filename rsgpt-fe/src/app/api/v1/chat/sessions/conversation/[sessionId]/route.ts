import { NextRequest, NextResponse } from 'next/server'
import { getAccessToken } from '@/lib/auth0'

const BASE = process.env.API_BASE_URL

export async function GET(req: NextRequest, { params }: { params: Promise<{ sessionId: string }> }) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const url = new URL(req.url)
    const sessionId = (await params).sessionId
    const qs = url.search // forwards ?page=...&page_size=...

    if (!sessionId) {
      return new NextResponse(JSON.stringify({ error: 'Session ID is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // Check if sessionId is a valid GUID format
    const guidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!guidRegex.test(sessionId)) {
      return NextResponse.json({ error: 'Session id not valid guid' }, { status: 404 })
    }

    const upstream = await fetch(`${BASE}/api/v1/chat/sessions/conversation/${sessionId}${qs}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })

    if (!upstream.ok) {
      if (upstream.status === 404 || upstream.status === 422) {
        return NextResponse.json({ error: 'Session not found' }, { status: 404 })
      }
      return NextResponse.json({ error: 'Failed to fetch session history' }, { status: upstream.status })
    }

    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    console.error('Session history API error:', error);
    return NextResponse.json({ error: 'Service temporarily unavailable. Please try again later.' }, { status: 503 })
  }
}
