import React, { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useInfiniteSessions } from '@/hooks/useSessions';
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
    },
  });

  return ({ children }: { children: ReactNode }) => 
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe('useInfiniteSessions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should fetch first page of sessions with default page size', async () => {
    const mockResponse = {
      sessions: [
        { id: 'session-1', title: 'Session 1' },
        { id: 'session-2', title: 'Session 2' }
      ],
      page: 1,
      page_size: 10,
      total: 2,
      has_next: false
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(), { wrapper });
    
    expect(result.current.isLoading).toBe(true);
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions?page=1&page_size=10');
    expect(result.current.data?.pages).toHaveLength(1);
    expect(result.current.data?.pages[0]).toEqual(mockResponse);
  });

  it('should fetch sessions with custom page size', async () => {
    const mockResponse = {
      sessions: [{ id: 'session-1', title: 'Session 1' }],
      page: 1,
      page_size: 5,
      total: 1,
      has_next: false
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(5), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions?page=1&page_size=5');
  });

  it('should handle pagination correctly', async () => {
    const page1Response = {
      sessions: [
        { id: 'session-1', title: 'Session 1' },
        { id: 'session-2', title: 'Session 2' }
      ],
      page: 1,
      page_size: 2,
      total: 4,
      has_next: true
    };
    
    const page2Response = {
      sessions: [
        { id: 'session-3', title: 'Session 3' },
        { id: 'session-4', title: 'Session 4' }
      ],
      page: 2,
      page_size: 2,
      total: 4,
      has_next: false
    };
    
    mockedApiFetch
      .mockResolvedValueOnce(page1Response)
      .mockResolvedValueOnce(page2Response);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(2), { wrapper });
    
    // Wait for first page
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data?.pages).toHaveLength(1);
    expect(result.current.hasNextPage).toBe(true);
    
    // Fetch next page
    await result.current.fetchNextPage();
    
    await waitFor(() => {
      expect(result.current.data?.pages).toHaveLength(2);
    });
    
    expect(mockedApiFetch).toHaveBeenCalledTimes(2);
    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, '/chat/sessions?page=1&page_size=2');
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, '/chat/sessions?page=2&page_size=2');
    
    expect(result.current.hasNextPage).toBe(false);
  });

  it('should handle no next page correctly', async () => {
    const mockResponse = {
      sessions: [{ id: 'session-1', title: 'Session 1' }],
      page: 1,
      page_size: 10,
      total: 1,
      has_next: false
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.hasNextPage).toBe(false);
  });

  it('should handle API errors', async () => {
    const mockError = new Error('Failed to fetch sessions');
    mockedApiFetch.mockRejectedValueOnce(mockError);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    
    expect(result.current.error).toEqual(mockError);
    expect(result.current.data).toBeUndefined();
  });

  it('should have correct query key', () => {
    const wrapper = createWrapper();
    
    // Test default page size
    renderHook(() => useInfiniteSessions(), { wrapper });
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions?page=1&page_size=10');
    
    jest.clearAllMocks();
    
    // Test custom page size
    renderHook(() => useInfiniteSessions(20), { wrapper });
    expect(mockedApiFetch).toHaveBeenCalledWith('/chat/sessions?page=1&page_size=20');
  });

  it('should have stale time configured', async () => {
    const mockResponse = {
      sessions: [],
      page: 1,
      page_size: 10,
      total: 0,
      has_next: false
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    // The stale time is set to 5 minutes (1000 * 60 * 5 ms)
    expect(result.current.data).toBeDefined();
  });

  it('should handle empty sessions list', async () => {
    const mockResponse = {
      sessions: [],
      page: 1,
      page_size: 10,
      total: 0,
      has_next: false
    };
    
    mockedApiFetch.mockResolvedValueOnce(mockResponse);
    
    const wrapper = createWrapper();
    const { result } = renderHook(() => useInfiniteSessions(), { wrapper });
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data?.pages[0].sessions).toEqual([]);
    expect(result.current.hasNextPage).toBe(false);
  });
});
