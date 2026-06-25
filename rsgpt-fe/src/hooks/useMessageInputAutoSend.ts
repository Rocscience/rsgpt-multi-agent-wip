'use client';

import { useEffect, useState } from 'react';
import { useMessageInputState } from '@/hooks/useMessageInputState';

interface UseMessageInputAutoSendProps {
  shouldAutoSend: boolean;
  onSubmit: ((text: string, sources: string[]) => void) | null;
  clearTextTrigger: number;
  setText: (text: string) => void;
}

interface UseMessageInputAutoSendReturn {
  sources: string[];
  setSources: (sources: string[]) => void;
}

/**
 * Hook to manage MessageInput initialization and auto-send:
 * - URL parameter sources reading
 * - Auto-send triggering
 * - Clear text trigger handling
 */
export const useMessageInputAutoSend = ({
  shouldAutoSend,
  onSubmit,
  clearTextTrigger,
  setText,
}: UseMessageInputAutoSendProps): UseMessageInputAutoSendReturn => {
  const [sources, setSources] = useState<string[]>(['ROC']);

  // Read sources from URL parameters when component mounts
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const urlSources = urlParams.get('sources');
      if (urlSources) {
        const newSources = urlSources.split(',').filter(Boolean);
        setSources(newSources);
      }
    }
  }, []);

  // Clear text when clearTextTrigger changes
  useEffect(() => {
    if (clearTextTrigger > 0) {
      setText('');
      // Emit event to reset scroll button position when text is cleared
      // This ensures the scroll button returns to its default position
      window.dispatchEvent(new CustomEvent('message-input-reset'));
    }
  }, [clearTextTrigger, setText]);

  // Auto-send when shouldAutoSend is triggered
  useEffect(() => {
    if (shouldAutoSend && onSubmit) {
      const { initialText } = useMessageInputState.getState();
      if (initialText && initialText.trim()) {
        setTimeout(() => {
          onSubmit(initialText.trim(), sources);
          // Reset the auto-send trigger to prevent duplicate sends
          useMessageInputState.getState().clear();
        }, 500); // 500ms delay to ensure everything is loaded
      }
    }
  }, [shouldAutoSend, onSubmit, sources]);

  return {
    sources,
    setSources,
  };
};

