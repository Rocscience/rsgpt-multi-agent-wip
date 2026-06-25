'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { notFound } from 'next/navigation';
import { useGetChatSessionHistory } from '@/hooks/useGetChatSessionHistory';
import { usePendingFirstMessage } from '@/hooks/usePendingFirstMessage';
import { useStreamPrompt } from '@/hooks/useStreamPrompt';
import { useMessageInputState } from '@/hooks/useMessageInputState';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useModelSelection } from '@/hooks/useModelSelection';
import { useContextUsage } from '@/hooks/useContextUsage';
import { MessageList } from '@/components/chat/messages/message-list';
import { StreamingErrorAlert, NetworkInterruptionAlert } from '@/components/alerts/alerts';
import { useAgentMode } from '@/hooks/useAgentMode';
import { useDeviceSelection } from '@/hooks/useDeviceSelection';
import { useSourceList } from '@/hooks/useSourceList';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

export default function ChatSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  
  // Early validation - check GUID format immediately
  const isValidGuidFormat = Boolean(sessionId?.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i));
  
  // If invalid format, show not-found immediately
  useEffect(() => {
    if (sessionId && !isValidGuidFormat) {
      notFound();
    }
  }, [sessionId, isValidGuidFormat]);

  const { sendMessage } = useStreamPrompt(sessionId);
  const pending = usePendingFirstMessage();
  const { selectedModel } = useModelSelection();
  const { isAgentMode, isWebSearch } = useAgentMode();
  const { selectedDeviceId } = useDeviceSelection();
  const { setPosition, setOnSubmit, setDisabled, clearText } = useMessageInputState();
  const { 
    getConversationTurns, 
    mergeConversationTurns,
    getCurrentStreamingTurn,
    isSessionStreaming
  } = useChatMessages();
  const { setVisible, clearSources } = useSourceList();
  const { 
    data: historyData, 
    fetchNextPage, 
    hasNextPage, 
    isFetchingNextPage,
    error: historyError,
    refetch
  } = useGetChatSessionHistory(sessionId);

  // Handle session not found errors from API (404, 422, etc.)
  useEffect(() => {
    if (historyError) {
      const errorMessage = historyError.message.toLowerCase();
      // Handle various session error scenarios
      if (
        errorMessage.includes('session not found') ||
        errorMessage.includes('422') ||
        errorMessage.includes('404') ||
        errorMessage.includes('unprocessable') ||
        errorMessage.includes('invalid session') ||
        errorMessage.includes('session id')
      ) {
        // Disable input before redirecting to not-found
        setDisabled(true);
        notFound();
      }
    }
  }, [historyError, setDisabled]);
  
  const started = useRef(false);
  const processedPending = useRef(false);
  const handleSubmitRef = useRef<(text: string, sources: string[]) => void>(() => {});

  // Get conversation turns and current streaming turn from global store
  const conversationTurns = getConversationTurns(sessionId);
  const currentStreamingTurn = getCurrentStreamingTurn(sessionId);


  // Hide sources sidebar when navigating to a new chat
  useEffect(() => {
    setVisible(false);
  }, [sessionId, setVisible]);

  // Add cleanup for browser close/refresh
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Abort any active streams when page is closing
      const { streamState } = useChatMessages.getState();
      if (streamState.isStreaming && streamState.streamAbortController) {
        streamState.streamAbortController.abort();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // State for streaming error handling
  const [streamingError, setStreamingError] = useState<string | null>(null);
  const [isNetworkError, setIsNetworkError] = useState(false);
  const [retryMessageData, setRetryMessageData] = useState<{ text: string; sources: string[] } | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  
  // Track online status for retry button
  useEffect(() => {
    setIsOnline(navigator.onLine);
    
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  // Watch for network interruption errors from the streaming response
  useEffect(() => {
    const aiError = currentStreamingTurn?.aiResponse?.error;
    if (aiError && aiError.includes('Connection lost')) {
      // Get the last user message text for retry
      const lastUserMessage = currentStreamingTurn?.userMessage?.message_text;
      const lastSources = currentStreamingTurn?.userMessage?.sources_requested || ['ROC'];
      
      if (lastUserMessage) {
        setStreamingError('Connection lost');
        setIsNetworkError(true);
        setRetryMessageData({ text: lastUserMessage, sources: lastSources });
        // Suppress the global offline alert
        useNetworkStatus.getState().setSuppressOfflineAlert(true);
      }
    }
  }, [currentStreamingTurn?.aiResponse?.error, currentStreamingTurn?.userMessage]);

  // If we arrived from /chat with a pending first message, kick off the stream.
  useEffect(() => {
    if (started.current) return;
    if (!pending.text) return;

    started.current = true;
    processedPending.current = true;

      // Send message using the global store (handles optimistic UI)
      // Use the pending model if available, otherwise use the current selected model
      const modelToUse = pending.selectedModel;
      sendMessage(pending.text, pending.sources, modelToUse, isAgentMode, selectedDeviceId, isWebSearch);
      
      // Note: Quota is refetched in useStreamPrompt when the stream completes
      
      pending.clear();
  }, [pending, sendMessage, isAgentMode, selectedDeviceId, isWebSearch]);

  // Load existing chat history if we're not coming from /chat with a pending message
  useEffect(() => {
    if (pending.text) return; // Skip if we have a pending message from /chat
    if (processedPending.current) return; // Skip if we already processed a pending message
    const pages = historyData?.pages;
    if (!pages?.length) return;
  
    const historyTurns = [...pages]                    // pages are newest→older
      .reverse()                                       // now oldest page → newest page
      .flatMap(page =>
        [...page.conversation]                         // conversation turns newest→oldest
          .reverse()                                   // now oldest→newest
      );
  
    // Use merge instead of set to preserve any locally streamed messages
    mergeConversationTurns(sessionId, historyTurns);
    
    // Initialize context usage if current_token_count is available
    const firstPage = pages[0];
    if (firstPage?.current_token_count !== undefined && selectedModel) {
      const { setFromHistory } = useContextUsage.getState();
      setFromHistory(firstPage.current_token_count, selectedModel, sessionId);
    }
  }, [historyData?.pages, pending.text, sessionId, mergeConversationTurns, selectedModel]);

  // Recalculate context usage percentage when model changes
  useEffect(() => {
    const { totalTokens, sessionId: contextSessionId, recalculateForModel } = useContextUsage.getState();
    
    // Only recalculate if:
    // 1. We have context usage data (totalTokens > 0)
    // 2. The context is for this session
    // 3. We have a selected model
    if (totalTokens > 0 && contextSessionId === sessionId && selectedModel) {
      recalculateForModel(selectedModel);
    }
  }, [selectedModel, sessionId]);

  // Clear context usage when navigating to a different session
  useEffect(() => {
    const { sessionId: contextSessionId, clearContextUsage } = useContextUsage.getState();
    
    // If we have context usage for a different session, clear it
    if (contextSessionId && contextSessionId !== sessionId) {
      clearContextUsage();
    }
  }, [sessionId]);

  // Check for ongoing streams when returning to a session
  useEffect(() => {
    // Skip if we have a pending message (new session)
    if (pending.text) return;
    
    const currentStreamingTurn = getCurrentStreamingTurn(sessionId);
    
    if (!currentStreamingTurn) {
      return;
    }
    
    // If we have a streaming turn but no active stream, it means we returned to a session
    // where streaming was happening but got disconnected.
    
    // Check if the AI response is still marked as loading but there's no active stream
    // This indicates a disconnected stream that needs to be handled
    if (currentStreamingTurn.aiResponse?.isLoading && !isSessionStreaming(sessionId)) {
      // Mark the AI response as no longer loading to stop the spinner
      const { updateStreamingAIResponse } = useChatMessages.getState();
      updateStreamingAIResponse(sessionId, { 
        isLoading: false, 
        isComplete: false 
      });
    }
    
    // Check if the stream might have completed while we were away by refetching latest history
    // This ensures we pick up any completed responses that were written to the database
    if (historyData && !isSessionStreaming(sessionId)) {
      refetch();
    }
  }, [sessionId, getCurrentStreamingTurn, isSessionStreaming, historyData, refetch]);

  const handleSubmit = useCallback(async (text: string, sources: string[]) => {
    try {
      // Clear any previous streaming errors
      setStreamingError(null);
      setRetryMessageData(null);
      
      // Clear source list when sending new message
      clearSources();
      
      // Clear input immediately on submit since we're adding to messages optimistically
      clearText();
      
      // Send message using the global store (handles optimistic UI and streaming)
      sendMessage(text, sources, selectedModel, isAgentMode, selectedDeviceId, isWebSearch);

      // Note: Quota is refetched in useStreamPrompt when the stream completes

      // Trigger spacer to push user message to top, then scroll
      setTimeout(() => {
        // Dispatch event to add spacer
        window.dispatchEvent(new Event('message-submitted'));
        
        // Wait a bit for spacer to be added, then scroll
        setTimeout(() => {
          const userMessages = document.querySelectorAll('[data-user-message]');
          if (userMessages.length > 0) {
            const lastUserMessage = userMessages[userMessages.length - 1];
            lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 100);
      }, 50);

    } catch (error) {
      // Handle any other errors that might occur
      console.error('Submit error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      
      // Check if this is a network interruption error (we use 'network_interrupted' as a code)
      const isNetwork = errorMessage === 'network_interrupted';
      
      setStreamingError(isNetwork ? 'Connection lost' : errorMessage);
      setIsNetworkError(isNetwork);
      setRetryMessageData({ text, sources });
      
      // Suppress the global offline alert when showing stream-specific network error
      if (isNetwork) {
        useNetworkStatus.getState().setSuppressOfflineAlert(true);
      }
      
      // Note: Quota is refetched in useStreamPrompt error handlers
    }
  }, [sendMessage, clearText, selectedModel, isAgentMode, selectedDeviceId, isWebSearch, clearSources]);

  // Keep ref updated with latest handleSubmit
  handleSubmitRef.current = handleSubmit;

  // Create a stable function reference
  const stableHandleSubmit = useCallback((text: string, sources: string[]) => {
    handleSubmitRef.current?.(text, sources);
  }, []);

  // Handle retry when streaming error occurs
  const handleRetryMessage = useCallback(() => {
    if (retryMessageData) {
      setIsRetrying(true);
      // Clear error state before retry
      setStreamingError(null);
      setIsNetworkError(false);
      // Re-enable global offline alert
      useNetworkStatus.getState().setSuppressOfflineAlert(false);
      
      handleSubmit(retryMessageData.text, retryMessageData.sources);
      // Reset retry state and data when submit completes
      setTimeout(() => {
        setIsRetrying(false);
        setRetryMessageData(null);
      }, 100);
    }
  }, [retryMessageData, handleSubmit]);

  // Handle error dismissal
  const handleDismissStreamingError = useCallback(() => {
    setStreamingError(null);
    setIsNetworkError(false);
    setRetryMessageData(null);
    // Re-enable the global offline alert
    useNetworkStatus.getState().setSuppressOfflineAlert(false);
  }, []);

  // Configure the shared MessageInput for this page - only if session format is valid
  useEffect(() => {
    if (sessionId && isValidGuidFormat) {
      setPosition('bottom');
      setDisabled(false);
      setOnSubmit(stableHandleSubmit);
    } else if (sessionId && !isValidGuidFormat) {
      // Hide/disable input for invalid sessions
      setPosition('hidden');
      setDisabled(true);
      setOnSubmit(() => {});
    }
    // Don't do anything if sessionId is not available yet
  }, [sessionId, isValidGuidFormat, setPosition, setDisabled, setOnSubmit, stableHandleSubmit]);

  return (
    <div className="relative flex h-full flex-col">
    
      <MessageList 
        conversationTurns={conversationTurns}
        currentStreamingTurn={currentStreamingTurn}
        onLoadMore={fetchNextPage}
        hasMore={hasNextPage}
        isLoading={isFetchingNextPage}
        sessionId={sessionId}
      />
      
      {/* Navigation Loading Overlay */}
      {/* <NavigationOverlay /> */}
      
      {/* Streaming Error Alert */}
      {streamingError && (
        <div className="fixed top-4 right-4 z-[60] max-w-md">
          {isNetworkError ? (
            <NetworkInterruptionAlert
              onRetry={handleRetryMessage}
              onDismiss={handleDismissStreamingError}
              isLoading={isRetrying}
              isOnline={isOnline}
            />
          ) : (
            <StreamingErrorAlert
              onRetry={handleRetryMessage}
              onDismiss={handleDismissStreamingError}
              isLoading={isRetrying}
            />
          )}
        </div>
      )}
    </div>
  );
}
