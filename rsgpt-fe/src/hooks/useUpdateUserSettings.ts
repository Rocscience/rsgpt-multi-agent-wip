'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { UserSettingsRequest, UserSettingsResponse } from '@/lib/types';

export function useUpdateUserSettings() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: UserSettingsRequest) =>
      apiFetch<UserSettingsResponse>('/user/settings', {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      // keep user settings fresh
      qc.invalidateQueries({ queryKey: ['user-settings'] });
    },
  });
}
