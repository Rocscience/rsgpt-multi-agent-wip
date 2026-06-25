import { getAccessToken } from '@/lib/auth0'
import { NextRequest } from 'next/server'

const BASE = process.env.API_BASE_URL

/**
 * Submit a quota request for additional agent quota
 */
export async function POST(request: NextRequest) {
  try {
    const token = await getAccessToken()
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const body = await request.json()

    const upstream = await fetch(`${BASE}/api/v1/user/quota-request`, {
      method: 'POST',
      headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!upstream.ok) {
      const errorData = await upstream.text()
      return new Response(errorData, {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (error) {
    console.error('Quota request API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Service temporarily unavailable. Please try again later.' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
