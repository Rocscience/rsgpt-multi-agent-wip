'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { QuotaRequestCreate, QuotaRequestResponse } from '@/lib/types';

export function useRequestQuota() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: QuotaRequestCreate) =>
      apiFetch<QuotaRequestResponse>('/user/quota-request', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      // Invalidate quota info to refresh the display
      queryClient.invalidateQueries({ queryKey: ['quota/info'] });
    },
  });
}
