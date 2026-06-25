// app/chat/page.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useCreateSession } from '@/hooks/useCreateSession';
import { usePendingFirstMessage } from '@/hooks/usePendingFirstMessage';
import { useMessageInputState } from '@/hooks/useMessageInputState';
import { useModelSelection } from '@/hooks/useModelSelection';
import { useSourceList } from '@/hooks/useSourceList';
import { useContextUsage } from '@/hooks/useContextUsage';
import { useEffect, useCallback, useRef, useState } from 'react';
import { SessionCreationErrorAlert } from '@/components/alerts/alerts';
import { NavigationOverlay } from '@/components/chat/navigation/navigation-overlay';

export default function NewChatPage() {
  const router = useRouter();
  const createSession = useCreateSession();
  const setPending = usePendingFirstMessage((s) => s.set);
  const { selectedModel } = useModelSelection();

  const { setPosition, setOnSubmit, setDisabled, clearText, setInitialText } = useMessageInputState();
  const { clearSources } = useSourceList();
  const handleSubmitRef = useRef<(text: string, sources: string[]) => void>(() => {});
  
  // State for error handling
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [retryData, setRetryData] = useState<{ text: string; sources: string[] } | null>(null);
  // State to control heading visibility
  const [showHeading, setShowHeading] = useState(true);

  // State for URL parameters
  const [prompt, setPrompt] = useState<string | null>(null);
  const [sources, setSources] = useState<string | null>(null);

  const handleSubmit = useCallback(async (text: string, sources: string[]) => {
    try {
      // Clear any previous errors
      setSessionError(null);
      setRetryData(null);
      
      // Clear source list when starting new chat
      clearSources();
      
      // Hide the message immediately
      setShowHeading(false);
      
      // 1) Keep the first message so it appears immediately on the session page
      setPending({ text, sources, selectedModel });

      // 2) Start session creation and animate to bottom position
      setPosition('bottom'); // This triggers the Framer Motion layout animation
      
      // 3) Create session and navigate
      // Strip @[filepath] patterns from title to make it user-friendly
      const cleanTitle = text.replace(/@\[([^\]]+)\]/g, '').trim().slice(0, 60) || undefined;
      const res = await createSession.mutateAsync({ title: cleanTitle });
      
      // Note: Quota is refetched in useStreamPrompt when the stream completes
      
      // Clear the input text only on success
      clearText();
      
      router.push(`/chat/${res.id}`);
    } catch (error) {
      // Handle session creation error
      console.error('Session creation failed:', error);
      
      // Reset position back to center for retry
      setPosition('center');
      
      // Show the message again on error
      setShowHeading(true);
      
      // Store error and retry data
      setSessionError(error instanceof Error ? error.message : 'Failed to create session');
      setRetryData({ text, sources });
    }
  }, [setPending, setPosition, createSession, router, clearText, selectedModel, clearSources]);

  // Keep ref updated with latest handleSubmit
  handleSubmitRef.current = handleSubmit;

  // Create a stable function reference
  const stableHandleSubmit = useCallback((text: string, sources: string[]) => {
    handleSubmitRef.current?.(text, sources);
  }, []);

  // Handle retry when error occurs
  const handleRetry = useCallback(() => {
    if (retryData) {
      handleSubmit(retryData.text, retryData.sources);
    }
  }, [retryData, handleSubmit]);

  // Handle error dismissal
  const handleDismissError = useCallback(() => {
    setSessionError(null);
    setRetryData(null);
  }, []);

  // Read URL parameters on client side
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      setPrompt(urlParams.get('prompt'));
      setSources(urlParams.get('sources'));
    }
  }, []);

  useEffect(() => {
    // Set the input to center position and configure it for this page
    setPosition('center');
    setDisabled(false);
    setOnSubmit(stableHandleSubmit);
  }, [setPosition, setOnSubmit, setDisabled, stableHandleSubmit]);

  // Clear context usage when starting a new chat
  useEffect(() => {
    useContextUsage.getState().clearContextUsage();
  }, []);

  // Read URL parameter and pre-populate message input
  useEffect(() => {
    if (prompt) {
      setInitialText(decodeURIComponent(prompt));
      
      // If sources are provided, set them in the pending message
      if (sources) {
        const sourcesArray = sources.split(',').filter(Boolean);
        setPending({ text: decodeURIComponent(prompt), sources: sourcesArray, selectedModel });
      }
    }
  }, [prompt, sources, setInitialText, setPending, selectedModel]); 

  return (
    <div className="relative flex h-full items-center justify-center -translate-y-10 md:-translate-y-20 px-2 sm:px-4">
      <div className="w-full max-w-[768px]">
        {showHeading && (
          <p className="font-bold text-2xl md:text-3xl text-center mb-[200px] md:mb-10 px-2">Ready when you are.</p>
        )}
        
        {/* Error Alert */}
        {sessionError && (
          <div className="fixed top-16 sm:top-20 md:top-24 right-2 sm:right-4 z-[60] max-w-sm sm:max-w-md">
            <SessionCreationErrorAlert
              onRetry={handleRetry}
              onDismiss={handleDismissError}
              isLoading={createSession.isPending}
            />
          </div>
        )}
      </div>
      
      {/* Navigation Loading Overlay */}
      <NavigationOverlay />
    </div>
  );
}


