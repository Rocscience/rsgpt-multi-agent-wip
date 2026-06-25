'use client';

import { useUser } from '@auth0/nextjs-auth0';
import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

/**
 * Sets the Sentry user context when a user is authenticated.
 * This enables user identification in error reports and prefills
 * the Sentry feedback widget with user info.
 */
export function SentryUserSetter() {
  const { user, isLoading } = useUser();

  useEffect(() => {
    if (isLoading) return;

    if (user) {
      Sentry.setUser({
        id: user.sub ?? undefined,
        email: user.email ?? undefined,
        username: user.name ?? undefined,
      });
    } else {
      // Clear user context when logged out
      Sentry.setUser(null);
    }
  }, [user, isLoading]);

  return null;
}

