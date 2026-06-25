'use client';

import { useCallback, useEffect, useState } from 'react';
import { useChatMessages } from '@/hooks/useChatMessages';

interface UseMessageInputStatusProps {
  pathname: string | null;
}

interface UseMessageInputStatusReturn {
  isServiceDown: boolean;
  isStreaming: boolean;
  handleStopStream: () => void;
}

/**
 * Hook to manage MessageInput status:
 * - Service availability monitoring
 * - Streaming state checking
 * - Stream cancellation
 */
export const useMessageInputStatus = ({
  pathname,
}: UseMessageInputStatusProps): UseMessageInputStatusReturn => {
  const [isServiceDown, setIsServiceDown] = useState(false);

  // Check if the current session is streaming
  const isStreaming = useChatMessages(state => {
    const currentSessionId = pathname?.startsWith('/chat/') ? pathname.split('/')[2] : null;
    return currentSessionId ? state.isSessionStreaming(currentSessionId) : false;
  });

  // Monitor service availability events
  useEffect(() => {
    const handleServiceUnavailable = () => setIsServiceDown(true);
    const handleServiceRecovered = () => setIsServiceDown(false);

    window.addEventListener('service-unavailable', handleServiceUnavailable);
    window.addEventListener('service-recovered', handleServiceRecovered);

    return () => {
      window.removeEventListener('service-unavailable', handleServiceUnavailable);
      window.removeEventListener('service-recovered', handleServiceRecovered);
    };
  }, []);

  // Handle stream cancellation
  const handleStopStream = useCallback(() => {
    if (!isStreaming) return;
    
    // Get the proper cancel function from state
    const { streamState } = useChatMessages.getState();
    
    // Call the cancel function which properly cancels the reader and updates state
    if (streamState.streamCancelFunction) {
      streamState.streamCancelFunction();
    } else {
      // Fallback: if no cancel function is available, just abort and clear state
      console.warn('[MessageInput] No cancel function available, using fallback');
      streamState.streamAbortController?.abort();
      useChatMessages.getState().clearStreamState();
      
      const currentSessionId = pathname?.startsWith('/chat/') ? pathname.split('/')[2] : null;
      if (currentSessionId) {
        useChatMessages.getState().cancelStreaming(currentSessionId);
      }
    }
  }, [isStreaming, pathname]);

  return {
    isServiceDown,
    isStreaming,
    handleStopStream,
  };
};

