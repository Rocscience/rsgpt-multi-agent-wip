/**
 * Basic API functionality tests
 * Tests core apiFetch behavior without circuit breaker complexity
 */

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock AbortController
const mockAbort = jest.fn();
const mockAbortController = {
  abort: mockAbort,
  signal: { aborted: false }
};
global.AbortController = jest.fn(() => mockAbortController);

// Mock window.dispatchEvent
const mockDispatchEvent = jest.fn();
Object.defineProperty(window, 'dispatchEvent', {
  value: mockDispatchEvent,
  writable: true
});

// Mock API_PREFIX
jest.mock('@/lib/consts', () => ({
  API_PREFIX: '/api/v1'
}));

describe('API Basic Functionality', () => {
  // Import after mocks are set up
  let apiFetch: any;
  
  beforeAll(() => {
    const apiModule = require('@/lib/api');
    apiFetch = apiModule.apiFetch;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockClear();
    mockDispatchEvent.mockClear();
    mockAbort.mockClear();
  });

  describe('Successful Requests', () => {
    it('should make a successful GET request', async () => {
      const mockData = { id: 1, name: 'test' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockData)
      });

      const result = await apiFetch('/test');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/test', 
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          credentials: 'include',
          signal: mockAbortController.signal
        })
      );
      expect(result).toEqual(mockData);
    });

    it('should make a successful POST request', async () => {
      const mockData = { success: true };
      const requestBody = { name: 'test' };
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockData)
      });

      const result = await apiFetch('/test', {
        method: 'POST',
        body: JSON.stringify(requestBody)
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/test', 
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(requestBody),
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          credentials: 'include'
        })
      );
      expect(result).toEqual(mockData);
    });

    it('should merge custom headers', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue({})
      });

      await apiFetch('/test', {
        headers: {
          'Authorization': 'Bearer token'
        }
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/test', 
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'Authorization': 'Bearer token'
          })
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle 401 unauthorized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: jest.fn().mockResolvedValue('Unauthorized')
      });

      await expect(apiFetch('/test')).rejects.toThrow('Session expired');
      
      expect(mockDispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'session-expired'
        })
      );
    });

    it('should handle 404 not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        text: jest.fn().mockResolvedValue('Not Found')
      });

      await expect(apiFetch('/test')).rejects.toThrow('Resource not found');
    });

    it('should handle 500 server error', async () => {
      const errorMessage = 'Internal Server Error';
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: jest.fn().mockResolvedValue(errorMessage)
      });

      await expect(apiFetch('/test')).rejects.toThrow(errorMessage);
    });
  });

  describe('Request Configuration', () => {
    it('should include default headers and credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue({})
      });

      await apiFetch('/test');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/test', 
        expect.objectContaining({
          credentials: 'include',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          signal: expect.any(Object)
        })
      );
    });

    it('should construct correct URL paths', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue({})
      });

      await apiFetch('/users/123');

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/users/123', expect.any(Object));
    });
  });

  describe('JSON Response Handling', () => {
    it('should parse JSON responses', async () => {
      const mockData = { users: [1, 2, 3], total: 3 };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockData)
      });

      const result = await apiFetch('/users');
      expect(result).toEqual(mockData);
    });

    it('should handle empty responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue({})
      });

      const result = await apiFetch('/test');
      expect(result).toEqual({});
    });
  });
});
