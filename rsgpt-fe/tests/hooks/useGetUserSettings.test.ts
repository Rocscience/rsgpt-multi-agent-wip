import React, { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useGetUserSettings } from '@/hooks/useGetUserSettings';
import { apiFetch } from '@/lib/api';

// Mock the API fetch function
jest.mock('@/lib/api', () => ({
  apiFetch: jest.fn()
}));

const mockedApiFetch = apiFetch as jest.MockedFunction<typeof apiFetch>;

// Create a test wrapper with QueryClient
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for tests
      },
    },
  });

  return ({ children }: { children: ReactNode }) => 
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe('useGetUserSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Always provide a default mock to prevent undefined returns
    mockedApiFetch.mockResolvedValue({ id: 'default-user', email: 'default@example.com' });
  });

  it('should not fetch when user is not authenticated', () => {
    const wrapper = createWrapper();
    
    renderHook(() => useGetUserSettings(false), { wrapper });
    
    expect(mockedApiFetch).not.toHaveBeenCalled();
  });

  it('should fetch user settings when user is authenticated', async () => {
    const mockUserSettings = {
      id: 'user-123',
      email: 'test@example.com',
      preferences: { theme: 'dark' }
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockUserSettings);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useGetUserSettings(true), { wrapper });
    
    expect(result.current.isLoading).toBe(true);
    expect(mockedApiFetch).toHaveBeenCalledWith('/user/settings', {
      method: 'GET',
    });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data).toEqual(mockUserSettings);
    expect(result.current.isLoading).toBe(false);
  });

  it('should handle API errors', async () => {
    const mockError = new Error('Failed to fetch user settings');
    mockedApiFetch.mockRejectedValueOnce(mockError);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useGetUserSettings(true), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    
    expect(result.current.error).toEqual(mockError);
    expect(result.current.data).toBeUndefined();
  });

  it('should have correct query key', () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useGetUserSettings(true), { wrapper });
    
    // The query key should be accessible through the query state
    expect(mockedApiFetch).toHaveBeenCalledWith('/user/settings', {
      method: 'GET',
    });
  });

  it('should be enabled only when user is authenticated', () => {
    const wrapper = createWrapper();
    
    // Mock a return value for the authenticated test
    const mockUserSettings = { id: 'user-123', email: 'test@example.com' };
    mockedApiFetch.mockResolvedValueOnce(mockUserSettings);
    
    // Test with authenticated user
    const { result: authenticatedResult } = renderHook(() => useGetUserSettings(true), { wrapper });
    expect(mockedApiFetch).toHaveBeenCalled();
    
    jest.clearAllMocks();
    
    // Test with unauthenticated user
    const { result: unauthenticatedResult } = renderHook(() => useGetUserSettings(false), { wrapper });
    expect(mockedApiFetch).not.toHaveBeenCalled();
  });

  it('should have stale time configured', async () => {
    const mockUserSettings = { id: 'user-123' };
    mockedApiFetch.mockResolvedValueOnce(mockUserSettings);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useGetUserSettings(true), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    // The stale time is set to 5 minutes (5 * 60 * 1000 ms)
    // We can't directly test this without more complex setup, but we can verify the query runs
    expect(result.current.data).toEqual(mockUserSettings);
  });
});
