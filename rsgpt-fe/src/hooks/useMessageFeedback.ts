'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { MessageFeedbackRequest, MessageFeedbackResponse } from '@/lib/types';

export function useMessageFeedback() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ messageId, body }: { messageId: string; body: MessageFeedbackRequest }) =>
      apiFetch<MessageFeedbackResponse>(`/chat/sessions/feedback/${messageId}`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      // keep user settings fresh
      qc.invalidateQueries({ queryKey: ['message-feedback'] });
    },
  });
}
