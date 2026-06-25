'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { CreateChatSessionResponse } from '@/lib/types';

export function useCreateSession() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: { title?: string }) =>
      apiFetch<CreateChatSessionResponse>('/chat/sessions', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    // Skip global error handler - chat/page.tsx has custom SessionCreationErrorAlert
    meta: { skipGlobalErrorHandler: true },
    onSuccess: () => {
      // keep sidebar fresh
      qc.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}
