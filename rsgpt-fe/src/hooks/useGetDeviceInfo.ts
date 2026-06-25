'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { DeviceListResponse } from '@/lib/types';

export function useGetDeviceInfo(enabled: boolean = true) {
  return useQuery({
    queryKey: ['device-info'],
    queryFn: () => apiFetch<DeviceListResponse>('/devices', { method: 'GET' }),
    enabled,
  });
}