'use client';

import { useEffect, useRef } from 'react';
import { useUser } from '@auth0/nextjs-auth0';
import { useTheme } from 'next-themes';
import { useGetUserSettings } from '@/hooks/useGetUserSettings';

export function ThemeInitializer() {
  const { user, isLoading: userLoading } = useUser();
  const { setTheme } = useTheme();
  const hasInitialized = useRef(false);
  
  // Only fetch user settings when user is authenticated
  const { data: userSettings, isSuccess } = useGetUserSettings(!!user && !userLoading);

  useEffect(() => {
    // Only apply saved theme once on initial load, not on subsequent changes
    if (isSuccess && userSettings?.theme && !hasInitialized.current) {
      setTheme(userSettings.theme);
      hasInitialized.current = true;
    }
  }, [isSuccess, userSettings, setTheme]);

  // This component doesn't render anything
  return null;
}
