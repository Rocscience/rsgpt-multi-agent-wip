'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { GetRocPortalStatusResponse } from '@/lib/types';

export function useUpdateRocPortalStatus() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<GetRocPortalStatusResponse>('/user/rocportal-status', {
        method: 'PUT',
      }),
    onSuccess: () => {
      // keep sidebar fresh
      qc.invalidateQueries({ queryKey: ['rocportal-status'] });
    },
  });
}
