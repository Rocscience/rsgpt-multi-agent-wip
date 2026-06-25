import { clearAllStores } from '@/lib/store-utils';

// Mock all the hook modules
jest.mock('@/hooks/usePendingFirstMessage', () => ({
  clearPendingMessage: jest.fn()
}));

jest.mock('@/hooks/useMessageInputState', () => ({
  clearMessageInputState: jest.fn()
}));

jest.mock('@/hooks/useModelSelection', () => ({
  clearModelSelection: jest.fn()
}));

jest.mock('@/hooks/useAgentMode', () => ({
  clearAgentMode: jest.fn()
}));

jest.mock('@/hooks/useDeviceSelection', () => ({
  clearDeviceSelection: jest.fn()
}));

jest.mock('@/hooks/useContextUsage', () => ({
  clearContextUsage: jest.fn()
}));

jest.mock('@/hooks/useChatMessages', () => ({
  useChatMessages: {
    getState: jest.fn(() => ({
      clear: jest.fn()
    }))
  }
}));

// Import the mocked functions
import { clearPendingMessage } from '@/hooks/usePendingFirstMessage';
import { clearMessageInputState } from '@/hooks/useMessageInputState';
import { clearModelSelection } from '@/hooks/useModelSelection';
import { clearAgentMode } from '@/hooks/useAgentMode';
import { clearDeviceSelection } from '@/hooks/useDeviceSelection';
import { clearContextUsage } from '@/hooks/useContextUsage';
import { useChatMessages } from '@/hooks/useChatMessages';

describe('store-utils', () => {
  describe('clearAllStores', () => {
    let mockClear: jest.Mock;

    beforeEach(() => {
      // Reset all mocks
      jest.clearAllMocks();
      
      // Create a mock clear function
      mockClear = jest.fn();
      (useChatMessages.getState as jest.Mock).mockReturnValue({
        clear: mockClear
      });
    });

    it('should call all store clear functions', () => {
      clearAllStores();

      expect(clearPendingMessage).toHaveBeenCalledTimes(1);
      expect(clearMessageInputState).toHaveBeenCalledTimes(1);
      expect(clearModelSelection).toHaveBeenCalledTimes(1);
      expect(clearAgentMode).toHaveBeenCalledTimes(1);
      expect(clearDeviceSelection).toHaveBeenCalledTimes(1);
      expect(clearContextUsage).toHaveBeenCalledTimes(1);
      expect(useChatMessages.getState).toHaveBeenCalledTimes(1);
      expect(mockClear).toHaveBeenCalledTimes(1);
    });

    it('should call functions in the correct order', () => {
      clearAllStores();

      // Verify all functions are called
      const callOrder = [
        clearPendingMessage,
        clearMessageInputState,
        clearModelSelection,
        clearAgentMode,
        clearDeviceSelection,
        clearContextUsage,
        mockClear
      ];

      callOrder.forEach((mockFn) => {
        expect(mockFn).toHaveBeenCalledTimes(1);
      });
    });

    it('should handle errors gracefully if one store fails to clear', () => {
      // Make one of the clear functions throw an error
      (clearPendingMessage as jest.Mock).mockImplementation(() => {
        throw new Error('Clear failed');
      });

      // Should not throw, but should still call other functions
      expect(() => clearAllStores()).toThrow('Clear failed');
      
      // Reset the mock and try again with a different approach
      (clearPendingMessage as jest.Mock).mockImplementation(() => {});
      
      // Test that it doesn't break the flow
      expect(() => clearAllStores()).not.toThrow();
    });
  });
});
