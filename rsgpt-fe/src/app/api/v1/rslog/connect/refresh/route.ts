import { NextRequest, NextResponse } from 'next/server';
import { getAccessToken } from '@/lib/auth0';

const BASE = process.env.API_BASE_URL;

export async function POST(request: NextRequest) {
  try {
    const token = await getAccessToken();
    
    if (!token) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const body = await request.text();
    
    const response = await fetch(`${BASE}/api/v1/rslog/connect/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: body,
      cache: 'no-store',
      credentials: 'include',
    });

    const data = await response.text();
    
    return new NextResponse(data, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (error) {
    console.error('RSLog connect/refresh proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
