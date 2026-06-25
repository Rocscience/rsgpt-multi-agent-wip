'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { GetQuotaInfoResponse } from '@/lib/types';

export function useGetQuotaInfo(userAuthenticated: boolean = true) {
  return useQuery({
    queryKey: ['quota/info'],
    queryFn: () =>
      apiFetch<GetQuotaInfoResponse>('/user/quota-info', {
        method: 'GET',
      }),
    enabled: userAuthenticated,
    staleTime: 30 * 1000, // 30 seconds - shorter to ensure quota updates are reflected quickly
    meta: {
      // Skip global error handler - 404 is expected when user has no organization
      // This is handled by the PortalAccountAlert instead
      skipGlobalErrorHandler: true,
    },
  });
}
