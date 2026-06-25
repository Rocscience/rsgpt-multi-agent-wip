import { auth0, getAccessToken } from '@/lib/auth0';
import { GetRocPortalStatusResponse } from '@/lib/types';
import { NextResponse } from 'next/server';

/**
 * Update rocPortal status for the current user
 */
export async function PUT() {
  try {
    const session = await auth0.getSession()
    
    if (!session) {
      return NextResponse.json({ error: 'No session found' }, { status: 401 });
    }
    
    const token = await getAccessToken()
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    
    const upstream = await fetch(`${process.env.API_BASE_URL}/api/v1/user/rocportal-status`, {
      method: 'PUT',
      headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      cache: 'no-store',
    });

    if (!upstream.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch RocPortal status' },
        { status: upstream.status }
      );
    }

    const response = await upstream.json() as GetRocPortalStatusResponse

    // Update session with rocPortalAccess
    await auth0.updateSession({
      ...session,
      user: {
        ...session.user,
        rocPortalAccess: response.rocportal_status
      }
    });

    return NextResponse.json(response);
  } catch (error) {
    console.error('Error in rocportal-status API:', error);
    
    // Check if it's a connection error
    if (error && typeof error === 'object' && 'code' in error && error.code === 'ECONNREFUSED') {
      return NextResponse.json(
        { error: 'Service temporarily unavailable. Please try again later.' },
        { status: 503 }
      );
    }
    
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
