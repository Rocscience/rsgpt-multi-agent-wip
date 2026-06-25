import React, { ReactNode } from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCreateSession } from '@/hooks/useCreateSession';
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
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  // Mock the invalidateQueries method
  const originalInvalidateQueries = queryClient.invalidateQueries;
  queryClient.invalidateQueries = jest.fn().mockImplementation(originalInvalidateQueries);

  return {
    wrapper: ({ children }: { children: ReactNode }) => 
      React.createElement(QueryClientProvider, { client: queryClient }, children),
    queryClient
  };
};

describe('useCreateSession', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should create a session successfully', async () => {
    const mockResponse = {
      id: 'session-123',
      title: 'New Chat Session',
      created_at: new Date().toISOString()
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const { wrapper, queryClient } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    expect(result.current.isPending).toBe(false);
    
    act(() => {
      result.current.mutate({ title: 'New Chat Session' });
    });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: 'New Chat Session' }),
    });
    
    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.isPending).toBe(false);
    
    // Check that sessions query was invalidated
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['sessions'] });
  });

  it('should create a session without title', async () => {
    const mockResponse = {
      id: 'session-456',
      title: null,
      created_at: new Date().toISOString()
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    act(() => {
      result.current.mutate({});
    });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    
    expect(result.current.data).toEqual(mockResponse);
  });

  it('should handle API errors', async () => {
    const mockError = new Error('Failed to create session');
    mockedApiFetch.mockRejectedValueOnce(mockError);
    
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    act(() => {
      result.current.mutate({ title: 'Test Session' });
    });
    
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    
    expect(result.current.error).toEqual(mockError);
    expect(result.current.data).toBeUndefined();
  });

  it('should not invalidate queries on error', async () => {
    const mockError = new Error('API Error');
    mockedApiFetch.mockRejectedValueOnce(mockError);
    
    const { wrapper, queryClient } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    act(() => {
      result.current.mutate({ title: 'Test Session' });
    });
    
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    
    // Should not invalidate queries on error
    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });

  it('should handle multiple mutations', async () => {
    const mockResponse1 = { id: 'session-1', title: 'Session 1' };
    const mockResponse2 = { id: 'session-2', title: 'Session 2' };
    
    mockedApiFetch
      .mockResolvedValueOnce(mockResponse1)
      .mockResolvedValueOnce(mockResponse2);
    
    const { wrapper, queryClient } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    // First mutation
    act(() => {
      result.current.mutate({ title: 'Session 1' });
    });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data).toEqual(mockResponse1);
    
    // Reset mutation state
    act(() => {
      result.current.reset();
    });
    
    // Second mutation
    act(() => {
      result.current.mutate({ title: 'Session 2' });
    });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data).toEqual(mockResponse2);
    expect(queryClient.invalidateQueries).toHaveBeenCalledTimes(2);
  });

  it('should have correct initial state', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useCreateSession(), { wrapper });
    
    expect(result.current.isPending).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeNull();
  });
});
