'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { UserMessage } from './user-message';
import { AIMessage } from './ai-message';
import { Button, Spinner, Tooltip } from '@heroui/react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import type { ConversationTurnDto, UserMessageDto } from '@/lib/types';

// Custom event types for input events
interface MessageInputHeightChangeEvent extends CustomEvent {
  detail: { height: number };
}

type Props = {
  conversationTurns: ConversationTurnDto[];
  isTyping?: boolean;
  onLoadMore?: () => void;
  hasMore?: boolean;
  isLoading?: boolean;
  sessionId: string;
  currentStreamingTurn?: {
    userMessage: UserMessageDto;
    aiResponse?: {
      id: string;
      text: string;
      isLoading?: boolean;
      isComplete?: boolean;
      lookingForMedia?: boolean;
    };
  };
};

export function MessageList({ conversationTurns, onLoadMore, hasMore, isLoading, sessionId, currentStreamingTurn }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shouldScrollToBottom = useRef(true);
  const prevTurnsLength = useRef(conversationTurns.length);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const scrollPositionRef = useRef<{ top: number; height: number } | null>(null);
  const isLoadingMoreRef = useRef(false);
  // State for dynamic positioning based on input height
  const [inputHeight, setInputHeight] = useState(80); // Default height for the input
  const [isLargeScreen, setIsLargeScreen] = useState(false);
  const prevValuesRef = useRef({ inputHeight: 80, isLargeScreen: false });
  // Dynamic spacer to push latest message to top during streaming
  const [spacerHeight, setSpacerHeight] = useState(0);
  const initialSpacerHeightRef = useRef(0);
  const aiResponseRef = useRef<HTMLDivElement | null>(null);
  const prevSessionIdRef = useRef<string>(sessionId);
  const hasSubtractedForButtonsRef = useRef(false);

  // Check screen size on mount and resize for responsive adjustments
  useEffect(() => {
    const checkScreenSize = () => {
      setIsLargeScreen(window.innerWidth >= 1024);
    };
    
    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    
    return () => {
      window.removeEventListener('resize', checkScreenSize);
    };
  }, []);

  // Calculate responsive bottom positioning for scroll button
  const getScrollButtonBottom = useCallback(() => {
    const baseOffset = 100;
    const minBottom = 160;
    const maxBottom = 420; // Prevent button from going too high
    // Add extra spacing for smaller screens
    const screenAdjustment = isLargeScreen ? 0 : 50;
    return Math.min(maxBottom, Math.max(minBottom, inputHeight + baseOffset + screenAdjustment));
  }, [inputHeight, isLargeScreen]);

  // Calculate responsive bottom padding for message list
  const getMessageListBottomPadding = useCallback(() => {
    const baseOffset = 120;
    const minPadding = 150;
    const maxPadding = 400; // Prevent excessive padding
    // Add extra padding for larger screens
    const screenAdjustment = isLargeScreen ? 20 : 0;
    return Math.min(maxPadding, Math.max(minPadding, inputHeight + baseOffset + screenAdjustment));
  }, [inputHeight, isLargeScreen]);

  // Set initial CSS custom properties
  useEffect(() => {
    const scrollButtonBottom = getScrollButtonBottom();
    const messageListPadding = getMessageListBottomPadding();
    
    document.documentElement.style.setProperty('--scroll-button-bottom', `${scrollButtonBottom}px`);
    document.documentElement.style.setProperty('--message-list-padding', `${messageListPadding}px`);
  }, [getScrollButtonBottom, getMessageListBottomPadding]); // Only run once on mount

  // Update CSS custom properties when input height changes
  useEffect(() => {
    // Only update if values have actually changed
    if (prevValuesRef.current.inputHeight !== inputHeight || prevValuesRef.current.isLargeScreen !== isLargeScreen) {
      const scrollButtonBottom = getScrollButtonBottom();
      const messageListPadding = getMessageListBottomPadding();
      
      // Set CSS custom properties on the document root
      document.documentElement.style.setProperty('--scroll-button-bottom', `${scrollButtonBottom}px`);
      document.documentElement.style.setProperty('--message-list-padding', `${messageListPadding}px`);
      
      // Update previous values
      prevValuesRef.current = { inputHeight, isLargeScreen };
    }
  }, [inputHeight, isLargeScreen, getScrollButtonBottom, getMessageListBottomPadding]);

  // Listen for input height changes and reset events from MessageInput
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    const handleInputHeightChange = (event: MessageInputHeightChangeEvent) => {
      // Debounce height changes to prevent excessive updates
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        const height = event.detail.height;
        // Ensure height is reasonable (between 56px and 315px)
        if (height >= 56 && height <= 315) {
          setInputHeight(height);
        }
      }, 50);
    };

    const handleInputReset = () => {
      // Reset input height to default when message is sent
      // Small delay to ensure textarea has fully collapsed
      setTimeout(() => {
        setInputHeight(80);
      }, 100);
    };

    window.addEventListener('message-input-height-change', handleInputHeightChange as EventListener);
    window.addEventListener('message-input-reset', handleInputReset as EventListener);
    
    // Handler for message submission - add spacer to push message to top
    const handleMessageSubmitted = () => {
      if (containerRef.current) {
        const viewportHeight = window.innerHeight;
        const desiredPercentage = 0.75;
        const spacer = Math.floor(viewportHeight * desiredPercentage);
        
        initialSpacerHeightRef.current = spacer;
        setSpacerHeight(spacer);
        hasSubtractedForButtonsRef.current = false; // Reset flag for new message
      }
    };

    window.addEventListener('message-submitted', handleMessageSubmitted);

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('message-input-height-change', handleInputHeightChange as EventListener);
      window.removeEventListener('message-input-reset', handleInputReset as EventListener);
      window.removeEventListener('message-submitted', handleMessageSubmitted);
    };
  }, []);

  // Auto-scroll to bottom when new conversation turns arrive
  // NOTE: currentStreamingTurn removed from deps to prevent continuous scroll during streaming
  useEffect(() => {
    if (!containerRef.current) return;
    
    const container = containerRef.current;
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 100;
    const isInitialLoad = prevTurnsLength.current === 0 && conversationTurns.length > 0;
    
    // Scroll to bottom if we're already at bottom, it's the initial load, or new turns were added
    if (isAtBottom || shouldScrollToBottom.current || isInitialLoad) {
      // Use setTimeout to ensure DOM has updated
      setTimeout(() => {
        if (containerRef.current) {
          containerRef.current.scrollTo({
            top: containerRef.current.scrollHeight,
            behavior: 'smooth'
          });
        }
      }, 0);
      shouldScrollToBottom.current = false;
    }
    
    prevTurnsLength.current = conversationTurns.length;
  }, [conversationTurns]);

  // Reset spacer when session changes (switching chats)
  useEffect(() => {
    if (prevSessionIdRef.current !== sessionId) {
      setSpacerHeight(0);
      initialSpacerHeightRef.current = 0;
      hasSubtractedForButtonsRef.current = false;
      prevSessionIdRef.current = sessionId;
    }
  }, [sessionId]);

  // Reduce spacer to minimal value when streaming completes
  useEffect(() => {
    if (currentStreamingTurn?.aiResponse?.isComplete && 
        spacerHeight > 0 && 
        !hasSubtractedForButtonsRef.current) {
      hasSubtractedForButtonsRef.current = true;
      // Reduce to a minimal comfortable padding (150px) instead of keeping the full spacer
      // This matches how other chatbots work - minimal bottom space after completion
      setSpacerHeight(150);
    }
  }, [currentStreamingTurn?.aiResponse?.isComplete, spacerHeight]);

  // Dynamically adjust spacer as AI response grows
  useEffect(() => {
    // Only active while streaming (not complete)
    if (!currentStreamingTurn?.aiResponse || currentStreamingTurn.aiResponse.isComplete) {
      // Don't reset spacer height - keep the final dynamically calculated value
      // This prevents jumping when short messages complete
      return;
    }

    // Find the streaming AI response element
    const aiResponseElement = document.querySelector('[data-streaming-ai-response]') as HTMLElement;
    if (!aiResponseElement || initialSpacerHeightRef.current === 0) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const aiResponseHeight = entry.contentRect.height;
        const initialSpacer = initialSpacerHeightRef.current;
        const newSpacerHeight = Math.max(0, initialSpacer - aiResponseHeight);
        setSpacerHeight(newSpacerHeight);
      }
    });

    resizeObserver.observe(aiResponseElement);

    return () => {
      resizeObserver.disconnect();
    };
  }, [currentStreamingTurn]);

  // Handle scroll for infinite loading and scroll button visibility
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    
    const container = containerRef.current;
    
    // Check if user has scrolled up significantly to show scroll button
    const isNearBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 200;
    const shouldShowButton = !isNearBottom;
    
    // Only update state if the value would actually change to prevent unnecessary re-renders
    setShowScrollButton((prev) => prev !== shouldShowButton ? shouldShowButton : prev);
    
    // Load more when scrolled near the top
    if (onLoadMore && hasMore && !isLoading && !isLoadingMoreRef.current && container.scrollTop < 100) {
      // Store the current scroll position and height before loading
      const scrollHeight = container.scrollHeight;
      const scrollTop = container.scrollTop;
      
      // Store the current scroll position for restoration
      scrollPositionRef.current = { top: scrollTop, height: scrollHeight };
      
      // Set loading flag to prevent multiple requests
      isLoadingMoreRef.current = true;
      
      onLoadMore();
    }
  }, [onLoadMore, hasMore, isLoading, conversationTurns.length]);

  // Restore scroll position after new conversation turns are loaded
  useEffect(() => {
    if (scrollPositionRef.current && containerRef.current) {
      const { top, height } = scrollPositionRef.current;
      
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(() => {
        if (containerRef.current) {
          const newHeight = containerRef.current.scrollHeight;
          const heightDifference = newHeight - height;
          
          // Only restore scroll position if the user hasn't manually scrolled away
          const currentScrollTop = containerRef.current.scrollTop;
          const isStillNearTop = currentScrollTop < 150; // Allow some tolerance
          
          if (isStillNearTop) {
            // Restore scroll position to maintain the same content at the top
            containerRef.current.scrollTop = top + heightDifference;
          }
        }
        
        // Clear the stored position and reset loading flag
        scrollPositionRef.current = null;
        isLoadingMoreRef.current = false;
      });
    }
  }, [conversationTurns.length]);

  // Function to scroll to bottom smoothly
  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth'
      });
      // Delay to ensure scroll completes before hiding scroll button
      setTimeout(() => {
        setShowScrollButton(false);
      }, 500);
    }
  }, []);

  return (
    <div className="relative flex-1 overflow-hidden">
      <div 
        ref={containerRef}
        data-message-list
        className="h-full overflow-y-auto p-2 sm:p-4 !pt-18"
        style={{ 
          paddingBottom: spacerHeight > 0 ? '0px' : 'var(--message-list-padding, 180px)' 
        }}
        onScroll={handleScroll}
      >
        <div className="mx-auto w-full max-w-[768px] px-2 sm:px-4">
          {isLoading && (
            <div className="text-center py-4 text-muted-foreground border-b border-divider mb-4">
              <div className="flex items-center justify-center gap-2">
                <Spinner size="sm" color="default" />
                <span className="text-sm sm:text-base">Loading more messages...</span>
              </div>
            </div>
          )}
            {/* Render conversation turns */}
            {conversationTurns.map((turn) => {
              const latestAIResponse = turn.ai_responses.find(response => response.is_latest);
              
              return (
                <div key={turn.user_message.id}>
                  {/* User Message */}
                  <UserMessage
                    userMessage={turn.user_message}
                    isTemp={false}
                  />
                  
                  {/* AI Response (if exists) */}
                  {latestAIResponse && (
                    <AIMessage
                      aiResponse={latestAIResponse}
                      sessionId={sessionId}
                      isTemp={false}
                    />
                  )}
                </div>
              );
            })}
            
            {/* Current streaming turn (if any) */}
            {currentStreamingTurn && (
              <div key={`streaming-${currentStreamingTurn.userMessage.id}`}>
                {/* Streaming User Message */}
                <UserMessage
                  userMessage={currentStreamingTurn.userMessage}
                  isTemp={!!currentStreamingTurn.userMessage.client_temp_id}
                />
                
                {/* Streaming AI Response */}
                {currentStreamingTurn.aiResponse && (
                  <div 
                    data-streaming-ai-response
                    style={{ minHeight: '64px' }}
                  >
                    <AIMessage
                      streamingResponse={currentStreamingTurn.aiResponse}
                      sessionId={sessionId}
                      isTemp={true}
                    />
                  </div>
                )}
              </div>
            )}
            
            {/* Dynamic spacer to push latest message to top during streaming */}
            {spacerHeight > 0 && (
              <div 
                style={{ 
                  height: `${spacerHeight}px`, 
                  flexShrink: 0,
                  transition: 'height 0.3s ease-out'
                }} 
                aria-hidden="true"
              />
            )}
        </div>
      </div>
      
      {/* Scroll to bottom button with dynamic positioning based on input height */}
      {showScrollButton && (
        <div 
          id="scroll-to-bottom-button"
          className="pointer-events-none absolute inset-x-0 flex justify-center"
          style={{ 
            bottom: 'var(--scroll-button-bottom, 160px)' // Uses CSS custom property, falls back to 140px
          }}
        >
          <Tooltip content="Scroll to bottom" placement="top">
            <Button
              isIconOnly
              className="pointer-events-auto bg-secondary text-secondary-foreground shadow-lg z-10"
              radius="full"
              size="md"
              onPress={scrollToBottom}
            >
              <ChevronDownIcon className="w-5 h-5 text-muted-foreground" />
            </Button>
          </Tooltip>
        </div>
      )}
    </div>
  );
}
