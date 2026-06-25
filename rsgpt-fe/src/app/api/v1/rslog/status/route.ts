import { NextRequest, NextResponse } from 'next/server';
import { getAccessToken } from '@/lib/auth0';

const BASE = process.env.API_BASE_URL;

export async function GET(request: NextRequest) {
  try {
    const token = await getAccessToken();
    
    if (!token) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }
    
    const response = await fetch(`${BASE}/api/v1/rslog/status`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
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
    console.error('RSLog status proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
