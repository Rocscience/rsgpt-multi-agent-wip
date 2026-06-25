import { getAccessToken } from "@/lib/auth0"
import { NextRequest } from "next/server"

const BASE = process.env.API_BASE_URL

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ messageId: string }> }
) {
  try {
    const token = await getAccessToken()

    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // Extract messageId from URL params
    const { messageId } = await params;
    
    if (!messageId) {
      return new Response(JSON.stringify({ error: 'Message ID is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // Get the request body
    const body = await request.text()

    // Forward request to backend
    const backendResponse = await fetch(`${BASE}/api/v1/chat/sessions/feedback/${messageId}`, {
      method: 'POST',
      headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: body,
    })

    // Return backend response
    return new Response(await backendResponse.text(), {
      status: backendResponse.status,
      headers: { 'Content-Type': backendResponse.headers.get('Content-Type') ?? 'application/json' },
    })

  } catch (error) {
    console.error('Message feedback API error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
