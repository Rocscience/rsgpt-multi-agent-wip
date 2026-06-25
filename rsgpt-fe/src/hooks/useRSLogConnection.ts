'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import type { 
  RSLogConnectTokenRequest,
  RSLogVerifyRequest,
  RSLogTokenResponse,
  RSLogTwoFactorResponse,
  RSLogErrorResponse,
  RSLogConnectionStatus,
  RSLogSettingsResponse 
} from '@/lib/types';

// Hook to get RSLog connection status
export function useRSLogConnectionStatus(userAuthenticated: boolean) {
  return useQuery({
    queryKey: ['rslog-status'],
    queryFn: () =>
      apiFetch<RSLogConnectionStatus>('/rslog/status', {
        method: 'GET',
      }),
    enabled: userAuthenticated,
    staleTime: 0, // Always consider data stale to ensure fresh fetches
    refetchOnWindowFocus: true,
  });
}

// Hook to connect to RSLog (initial authentication)
export function useRSLogConnect() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: RSLogConnectTokenRequest) =>
      apiFetch<RSLogTokenResponse | RSLogTwoFactorResponse>('/rslog/connect/token', {
        method: 'POST',
        body: JSON.stringify(request),
      }),
    onSuccess: () => {
      // Invalidate status query to refresh connection state
      queryClient.invalidateQueries({ queryKey: ['rslog-status'] });
    },
  });
}

// Hook to verify 2FA code
export function useRSLogVerify() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: RSLogVerifyRequest) =>
      apiFetch<RSLogTokenResponse>('/rslog/connect/verify', {
        method: 'POST',
        body: JSON.stringify(request),
      }),
    onSuccess: () => {
      // Invalidate status query to refresh connection state
      queryClient.invalidateQueries({ queryKey: ['rslog-status'] });
    },
  });
}

// Hook to refresh RSLog token
export function useRSLogRefresh() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () =>
      apiFetch<RSLogSettingsResponse>('/rslog/connect/refresh', {
        method: 'POST',
      }),
    onSuccess: () => {
      // Invalidate status query to refresh connection state
      queryClient.invalidateQueries({ queryKey: ['rslog-status'] });
    },
  });
}

// Hook to disconnect RSLog
// Hook to enable RSLog (soft connect - no re-authentication needed)
export function useRSLogEnable() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () =>
      apiFetch<{ message: string }>('/rslog/connect/enable', {
        method: 'POST',
      }),
    onSuccess: () => {
      // Invalidate status query to refresh connection state
      queryClient.invalidateQueries({ queryKey: ['rslog-status'] });
    },
  });
}

export function useRSLogDisconnect() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () =>
      apiFetch<{ message: string }>('/rslog/disconnect', {
        method: 'DELETE',
      }),
    onSuccess: () => {
      // Invalidate status query to refresh connection state
      queryClient.invalidateQueries({ queryKey: ['rslog-status'] });
    },
  });
}

// Utility function to check if a response is a 2FA challenge
export function isRSLogTwoFactorResponse(
  response: RSLogTokenResponse | RSLogTwoFactorResponse
): response is RSLogTwoFactorResponse {
  return 'status' in response && 'twoFactorProvider' in response;
}

// Utility function to check if a response is an error
export function isRSLogErrorResponse(
  response: any
): response is RSLogErrorResponse {
  return response && 'error' in response && 'errorDescription' in response;
}
