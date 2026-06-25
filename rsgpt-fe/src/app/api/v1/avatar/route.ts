import { NextRequest, NextResponse } from 'next/server';

/**
 * Proxies external avatar images to avoid CORS issues.
 * Browser extensions that scan images can trigger CORS errors when
 * images are loaded from external domains like Gravatar.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');

  if (!url) {
    return new NextResponse('Missing url parameter', { status: 400 });
  }

  // Validate the URL is from an allowed domain
  const allowedDomains = [
    's.gravatar.com',
    'cdn.auth0.com',
    'lh3.googleusercontent.com',
  ];

  try {
    const parsedUrl = new URL(url);
    if (!allowedDomains.includes(parsedUrl.hostname)) {
      return new NextResponse('Domain not allowed', { status: 403 });
    }

    const response = await fetch(url);
    
    if (!response.ok) {
      return new NextResponse('Failed to fetch image', { status: response.status });
    }

    const contentType = response.headers.get('content-type') || 'image/png';
    const buffer = await response.arrayBuffer();

    return new NextResponse(buffer, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400', // Cache for 24 hours
      },
    });
  } catch {
    return new NextResponse('Invalid URL', { status: 400 });
  }
}

