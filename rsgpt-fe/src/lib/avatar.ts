/**
 * Returns a proxied URL for avatar images to avoid CORS issues.
 * External avatar images (from Gravatar, Auth0, Google) are proxied
 * through our API to prevent CORS errors from browser extensions.
 */
export function getProxiedAvatarUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  
  // Only proxy external URLs that might cause CORS issues
  const externalDomains = ['s.gravatar.com', 'cdn.auth0.com', 'lh3.googleusercontent.com'];
  
  try {
    const parsedUrl = new URL(url);
    if (externalDomains.includes(parsedUrl.hostname)) {
      return `/api/v1/avatar?url=${encodeURIComponent(url)}`;
    }
  } catch {
    // If URL parsing fails, return the original
    return url;
  }
  
  return url;
}

