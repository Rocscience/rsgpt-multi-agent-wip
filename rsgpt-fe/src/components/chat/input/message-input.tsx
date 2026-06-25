'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { MessageInputOptions } from './message-input-components/message-input-options';
import { ChipTextarea } from './message-input-components/chip-textarea';
import { AgentQuotaExceededBanner } from './agent-quota-exceeded-banner';
import { useMessageInputState } from '@/hooks/useMessageInputState';
import { useGetQuotaInfo } from '@/hooks/useGetQuotaInfo';
import { useAgentMode } from '@/hooks/useAgentMode';
import { useMessageInputUI } from '@/hooks/useMessageInputUI';
import { useMessageInputStatus } from '@/hooks/useMessageInputStatus';
import { useMessageInputAutoSend } from '@/hooks/useMessageInputAutoSend';
import { useUser } from '@auth0/nextjs-auth0';

// Regex to find file paths in format @[filepath]
const FILE_PATH_REGEX = /@\[([^\]]+)\]/g;

export const MessageInput = () => {
  const { position, disabled, onSubmit, clearTextTrigger, shouldAutoSend } = useMessageInputState();
  const pathname = usePathname();
  const [text, setText] = useState('');
  const { user } = useUser();
  
  // Count existing file paths in the message
  const filePathCount = useMemo(() => {
    const matches = text.match(FILE_PATH_REGEX);
    return matches ? matches.length : 0;
  }, [text]);
  
  // Check quota information based on mode
  const { data: quotaInfo } = useGetQuotaInfo(!!user);
  const { isAgentMode } = useAgentMode();
  
  // Check the appropriate quota based on current mode
  const isQuotaExceeded = quotaInfo 
    ? isAgentMode 
      ? quotaInfo.agent_quota_used >= quotaInfo.agent_quota
      : quotaInfo.questions_used >= quotaInfo.question_quota 
    : false;
  
  // Specifically track if agent quota is exceeded (for showing the banner)
  const isAgentQuotaExceeded = isAgentMode && quotaInfo && quotaInfo.agent_quota_used >= quotaInfo.agent_quota;
  
  // Check if we're on the New Chat page (chat route without session ID)
  const isNewChatPage = pathname === '/chat';
  
  // Custom hooks for UI behavior, status, and auto-send
  const { inputContainerRef, textareaRef } = useMessageInputUI({
    isNewChatPage,
    disabled: disabled || false,
    shouldDisableSubmit: disabled || false || isQuotaExceeded,
  });
  
  const { isServiceDown, isStreaming, handleStopStream } = useMessageInputStatus({
    pathname,
  });
  
  const { sources, setSources } = useMessageInputAutoSend({
    shouldAutoSend,
    onSubmit,
    clearTextTrigger,
    setText,
  });
  
  // Check network status for offline detection
  // Use local state synced with browser events directly
  const [isOnline, setIsOnline] = useState(true);
  
  useEffect(() => {
    // Set initial state on mount (client-side only)
    setIsOnline(navigator.onLine);
    
    // Sync with browser's online/offline events
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  // Separate states for typing vs submission
  // Disable typing only for account issues (quota, service down, session not available, offline)
  const shouldDisableTyping = disabled || isServiceDown || isQuotaExceeded || !isOnline;
  
  // Disable submission for account issues OR when streaming OR offline
  const shouldDisableSubmit = disabled || isServiceDown || isStreaming || isQuotaExceeded || !isOnline;

  const submitMessage = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || !onSubmit || shouldDisableSubmit) return;
    onSubmit(trimmed, sources);
    // Don't auto-clear - let the parent component decide when to clear
  }, [onSubmit, sources, text, shouldDisableSubmit]);

  // Handle file path selection
  const handleFilePathSelect = useCallback((filePath: string) => {
    // filePath is already formatted as @[path] from FilePathSelector
    setText(prev => prev ? `${prev} ${filePath}` : filePath);
  }, []);

  // Synchronous validation - check if we're on a session route with invalid session ID format
  const isSessionRoute = pathname?.match(/^\/chat\/([^\/]+)$/);
  const sessionId = isSessionRoute?.[1];
  const isInvalidSessionFormat = sessionId && !sessionId.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

  // Return early to prevent any rendering if conditions aren't met
  // Don't render if pathname is not available yet (prevents initial flicker)
  if (!pathname || position === 'hidden' || isInvalidSessionFormat) {
    return null;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submitMessage();
  }

  // Shared input content component
  const inputContent = (
    <>
      {/* Agent quota exceeded banner */}
      {isAgentQuotaExceeded && (
        <AgentQuotaExceededBanner
          currentQuota={quotaInfo?.agent_quota ?? 10}
          currentUsed={quotaInfo?.agent_quota_used ?? 0}
        />
      )}
      
    <div className="mx-auto w-full max-w-[768px] space-y-2 px-2 sm:px-4 transition-all duration-300">
      <div ref={inputContainerRef} className="flex items-center gap-2 py-2 px-2 shadow-lg bg-secondary rounded-3xl border-2 border-transparent focus:outline-none focus-within:border-default focus-within:ring-2 focus-within:ring-default/20 min-h-[60px] flex-row flex-wrap justify-between">

        {/* ChipTextarea */}
        <ChipTextarea
          tabIndex={0}
          ref={textareaRef}
          aria-label="Ask anything"
          value={text}
          onValueChange={setText}
          isDisabled={shouldDisableTyping}
          placeholder={
            !isOnline ? "You're offline" :
            isQuotaExceeded ? (isAgentMode ? "Agent quota exceeded" : "Question quota exceeded") :
            isServiceDown ? "Service temporarily unavailable" :
            disabled ? "Session not available" : 
            "Ask anything"
          }
          minRows={1}
          maxRows={13}
          variant="flat"
          className="order-1 px-1 grow-2"
          classNames={{
            inputWrapper:
              'bg-transparent shadow-none border-none p-0 data-[hover=true]:bg-transparent data-[focus=true]:bg-transparent focus-within:bg-transparent',
            innerWrapper: 'items-start',
            input: 'text-[0.975rem] placeholder:text-muted-foreground focus:outline-none focus:ring-0 focus:border-none',
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !shouldDisableSubmit) {
              e.preventDefault();
              submitMessage();
            }
          }}
        />

        {/* Mode Selection and Agent Options */}
        <MessageInputOptions 
          shouldDisableSubmit={shouldDisableSubmit}
          sources={sources}
          onSourcesChange={setSources}
          isStreaming={isStreaming}
          hasText={!!text.trim()}
          onStop={handleStopStream}
          onFilePathSelect={handleFilePathSelect}
          filePathCount={filePathCount}
        />
      </div>
    </div>
    </>
  );

  return (
    <>
      {position === 'bottom' && (
        <div className="absolute inset-x-0 bottom-0 z-30 h-40 pointer-events-none bg-gradient-to-t from-background to-transparent" />
      )}
      <motion.form
        layout
        onSubmit={handleSubmit}
        className={
          position === 'center'
            ? isNewChatPage
              ? "absolute inset-x-0 top-[44%] z-30 flex justify-center px-2 sm:px-4 pb-2"
              : "absolute inset-x-0 top-1/2 -translate-y-1/2 z-30 flex justify-center px-2 sm:px-4 pb-2"
            : "absolute inset-x-0 bottom-10 sm:bottom-6 z-30 flex justify-center px-2 sm:px-4 pointer-events-none pb-2"
        }
        transition={{ 
          type: "tween", 
          duration: 0.3,
          ease: "easeIn"
        }}
      >
        <motion.div
          layout
          className={
            position === 'center'
              ? "mx-auto w-full max-w-5xl pointer-events-auto"
              : "mx-auto w-full max-w-5xl pointer-events-auto"
          }
        >
          {inputContent}
        </motion.div>
      </motion.form>
    </>
  );
};

MessageInput.displayName = 'MessageInput';