import React from 'react';
import { render } from '@testing-library/react';
import { LogoutHandler } from '@/components/auth/logout-handler';
import { clearAllStores } from '@/lib/store-utils';

// Mock Auth0 NextJS components 
jest.mock('@auth0/nextjs-auth0', () => ({
  useUser: jest.fn(),
  UserProvider: ({ children }: any) => children,
}));

jest.mock('@/lib/store-utils');

// Import the mocked useUser after mocking
const { useUser } = require('@auth0/nextjs-auth0');

const mockUseUser = useUser as jest.MockedFunction<typeof useUser>;
const mockClearAllStores = clearAllStores as jest.MockedFunction<typeof clearAllStores>;

// Skip window.location.assign testing due to JSDOM complexity
// Focus on testing the event listener setup and clearAllStores functionality

describe('LogoutHandler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock window event listeners to track calls
    window.addEventListener = jest.fn();
    window.removeEventListener = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('session-expired event handling', () => {
    it('should set up session-expired event listener on mount', () => {
      mockUseUser.mockReturnValue({
        user: { sub: 'user123', name: 'Test User' },
        isLoading: false
      });

      render(<LogoutHandler />);

      expect(window.addEventListener).toHaveBeenCalledWith(
        'session-expired',
        expect.any(Function)
      );
    });

    it('should clean up session-expired event listener on unmount', () => {
      mockUseUser.mockReturnValue({
        user: { sub: 'user123', name: 'Test User' },
        isLoading: false
      });

      const { unmount } = render(<LogoutHandler />);
      
      // Get the event handler that was registered
      const addEventListenerCall = (window.addEventListener as jest.Mock).mock.calls
        .find(call => call[0] === 'session-expired');
      const eventHandler = addEventListenerCall[1];

      unmount();

      expect(window.removeEventListener).toHaveBeenCalledWith(
        'session-expired',
        eventHandler
      );
    });

    it('should handle session-expired event and call clearAllStores', () => {
      mockUseUser.mockReturnValue({
        user: { sub: 'user123', name: 'Test User' },
        isLoading: false
      });

      render(<LogoutHandler />);

      // Get the event handler that was registered
      const addEventListenerCall = (window.addEventListener as jest.Mock).mock.calls
        .find(call => call[0] === 'session-expired');
      const eventHandler = addEventListenerCall[1];

      // Simulate the event being fired
      eventHandler();

      expect(mockClearAllStores).toHaveBeenCalledTimes(1);
      // Note: window.location.assign is also called but difficult to test in JSDOM
    });
  });

  describe('existing Auth0 logout detection', () => {
    it('should clear stores when user naturally logs out via Auth0', () => {
      const { rerender } = render(<LogoutHandler />);

      // First render - user is logged in
      mockUseUser.mockReturnValue({
        user: { sub: 'user123', name: 'Test User' },
        isLoading: false
      });
      rerender(<LogoutHandler />);

      // Second render - user logs out
      mockUseUser.mockReturnValue({
        user: undefined,
        isLoading: false
      });
      rerender(<LogoutHandler />);

      expect(mockClearAllStores).toHaveBeenCalledTimes(1);
    });

    it('should not clear stores on initial load when no user', () => {
      mockUseUser.mockReturnValue({
        user: undefined,
        isLoading: false
      });

      render(<LogoutHandler />);

      expect(mockClearAllStores).not.toHaveBeenCalled();
    });
  });

  it('should render null', () => {
    mockUseUser.mockReturnValue({
      user: undefined,
      isLoading: false
    });

    const { container } = render(<LogoutHandler />);
    
    expect(container.firstChild).toBeNull();
  });
});
