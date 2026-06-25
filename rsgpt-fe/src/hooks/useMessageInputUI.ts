'use client';

import { useEffect, useRef, useState } from 'react';

interface UseMessageInputUIProps {
  isNewChatPage: boolean;
  disabled: boolean;
  shouldDisableSubmit: boolean;
}

interface UseMessageInputUIReturn {
  inputContainerRef: React.RefObject<HTMLDivElement | null>;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  isMultiLine: boolean;
}

/**
 * Hook to manage MessageInput UI behavior:
 * - Height tracking with ResizeObserver
 * - Multi-line detection
 * - Auto-focus management
 */
export const useMessageInputUI = ({
  isNewChatPage,
  disabled,
  shouldDisableSubmit,
}: UseMessageInputUIProps): UseMessageInputUIReturn => {
  const inputContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isMultiLine, setIsMultiLine] = useState(false);

  // Auto-focus the textarea when on the new chat page
  useEffect(() => {
    if (isNewChatPage && inputContainerRef.current && !disabled) {
      // Small delay to ensure the component is fully rendered
      const timer = setTimeout(() => {
        if (inputContainerRef.current) {
          inputContainerRef.current.focus();
        }
      }, 100);
      
      return () => clearTimeout(timer);
    }
  }, [isNewChatPage, disabled]);

  // Listen for focus requests (e.g., after AI response completes)
  useEffect(() => {
    const handleFocusRequest = () => {
      if (inputContainerRef.current && !shouldDisableSubmit) {
        // Small delay to ensure the component is ready
        setTimeout(() => {
          if (inputContainerRef.current) {
            inputContainerRef.current.focus();
          }
        }, 100);
      }
    };

    window.addEventListener('focus-message-input', handleFocusRequest);
    return () => window.removeEventListener('focus-message-input', handleFocusRequest);
  }, [shouldDisableSubmit]);

  // Measure input height and emit custom event for MessageList to listen to
  useEffect(() => {
    if (!inputContainerRef.current) return;
    
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.contentRect.height;
        // Only emit if height is valid and input is visible
        if (height > 0 && entry.target.getBoundingClientRect().height > 0) {
          window.dispatchEvent(new CustomEvent('message-input-height-change', {
            detail: { height }
          }));
        }
      }
    });
    
    resizeObserver.observe(inputContainerRef.current);
    
    // Emit initial height after a small delay to ensure DOM is ready
    setTimeout(() => {
      if (inputContainerRef.current) {
        const initialHeight = inputContainerRef.current.getBoundingClientRect().height;
        if (initialHeight > 0) {
          window.dispatchEvent(new CustomEvent('message-input-height-change', {
            detail: { height: initialHeight }
          }));
        }
      }
    }, 100);
    
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Monitor textarea for multi-line detection based on actual line count
  useEffect(() => {
    if (!textareaRef.current) return;
    
    const checkMultiLine = () => {
      if (!textareaRef.current) return;
      
      const textarea = textareaRef.current;
      const text = textarea.value;
      
      // Method 1: Count actual line breaks in text
      const lineBreaks = (text.match(/\n/g) || []).length;
      const hasLineBreaks = lineBreaks > 0;
      
      // Method 2: Check if scroll height exceeds client height (content overflows)
      const scrollHeight = textarea.scrollHeight;
      const clientHeight = textarea.clientHeight;
      const hasOverflow = scrollHeight > clientHeight;
      
      // Method 3: Check computed line height vs content height
      const computedStyle = window.getComputedStyle(textarea);
      const lineHeight = parseFloat(computedStyle.lineHeight);
      const actualLines = Math.round(scrollHeight / lineHeight);
      const hasMultipleLines = actualLines > 1;
      
      // Consider it multi-line if any method detects multiple lines
      const newIsMultiLine = hasLineBreaks || hasOverflow || hasMultipleLines;
      
      setIsMultiLine(newIsMultiLine);
    };
    
    // Check on text change
    const handleInput = () => {
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(checkMultiLine);
    };
    
    // Check on resize
    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(checkMultiLine);
    });
    
    // Add event listeners
    textareaRef.current.addEventListener('input', handleInput);
    textareaRef.current.addEventListener('paste', handleInput);
    resizeObserver.observe(textareaRef.current);
    
    // Initial check
    setTimeout(checkMultiLine, 100);
    
    return () => {
      if (textareaRef.current) {
        textareaRef.current.removeEventListener('input', handleInput);
        textareaRef.current.removeEventListener('paste', handleInput);
      }
      resizeObserver.disconnect();
    };
  }, []);

  return {
    inputContainerRef,
    textareaRef,
    isMultiLine,
  };
};

