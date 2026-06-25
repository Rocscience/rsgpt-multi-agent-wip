import { auth0, getAccessToken } from '@/lib/auth0';
import { NextRequest, NextResponse } from 'next/server';

// This route now returns the direct backend URL and token
// The frontend will connect directly to AWS, bypassing Vercel's streaming limits
// Benefits: No duration limits, no extra Vercel costs, lower latency

const API_BASE_URL = process.env.API_BASE_URL!;

export async function POST(req: NextRequest, { params }: { params: Promise<{ sessionId: string }> }) {
    try {
        // Get session without passing request (App Router API route pattern)
        const session = await auth0.getSession()
        
        if (!session) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        // Use the helper to get access token with automatic refresh
        const token = await getAccessToken()
        
        if (!token) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }
        
        const sessionId = (await params).sessionId
        
        if (!sessionId) {
            return NextResponse.json({ error: 'Session ID is required' }, { status: 400 })
        }

        // Check if sessionId is a valid GUID format
        const guidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!guidRegex.test(sessionId)) {
            return NextResponse.json({ error: 'Session not found' }, { status: 404 })
        }

        // Return the direct URL and token for the frontend to use
        // This bypasses Vercel entirely for the streaming connection
        return NextResponse.json({
            streamUrl: `${API_BASE_URL}/api/v1/chat/sessions/stream/${sessionId}`,
            token,
        })
    } catch (error) {
        console.error('Stream setup error:', error);
        return NextResponse.json({ 
            error: 'Service temporarily unavailable. Please try again later.' 
        }, { status: 503 })
    }
}
