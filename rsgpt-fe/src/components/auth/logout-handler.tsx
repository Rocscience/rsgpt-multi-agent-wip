'use client';

import { useUser } from '@auth0/nextjs-auth0';
import { useEffect, useRef } from 'react';
import { clearAllStores } from '@/lib/store-utils';

export function LogoutHandler() {
  const { user, isLoading } = useUser();
  const wasLoggedIn = useRef(false);

  useEffect(() => {
    if (user && !isLoading) {
      wasLoggedIn.current = true;
    }

    if (!user && !isLoading && wasLoggedIn.current) {
      clearAllStores();
      wasLoggedIn.current = false;
    }
  }, [user, isLoading]);

  // Handle session-expired events from API calls
  useEffect(() => {
    const handleSessionExpired = () => {
      clearAllStores();
      window.location.assign('/auth/logout');
    };

    window.addEventListener('session-expired', handleSessionExpired);

    return () => {
      window.removeEventListener('session-expired', handleSessionExpired);
    };
  }, []);

  return null;
}