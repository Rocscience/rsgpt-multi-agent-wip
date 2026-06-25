const BASE = process.env.API_BASE_URL

export async function GET() {
  try {

    const upstream = await fetch(`${BASE}/health`, {
      cache: 'no-store',
    })

    if (!upstream.ok) {
      return new Response(JSON.stringify({ error: 'Failed to fetch health' }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
    })
  } catch (error) {
    console.error('Health API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Service temporarily unavailable. Please try again later.' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
