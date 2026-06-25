'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { UserSettingsResponse } from '@/lib/types';

export function useGetUserSettings(userAuthenticated: boolean) {
  return useQuery({
    queryKey: ['user-settings'],
    queryFn: () =>
      apiFetch<UserSettingsResponse>('/user/settings', {
        method: 'GET',
      }),
    enabled: userAuthenticated,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
