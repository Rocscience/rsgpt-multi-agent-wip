'use client';

import { useEffect } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { Spinner } from '@heroui/react';
import { useNavigationState } from '@/hooks/useNavigationState';

export function NavigationOverlay() {
  const { isNavigating, targetSessionId, setNavigating } = useNavigationState();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const pathname = usePathname();

  // Clear navigation state when we reach the target session or new chat page
  useEffect(() => {
    if (isNavigating) {
      // Check if we've reached the target destination
      const isNewChatPage = pathname === '/chat';
      const isTargetSession = sessionId === targetSessionId;
      const isTargetNewChat = targetSessionId === 'new' && isNewChatPage;
      
      if (isTargetSession || isTargetNewChat) {
          setNavigating(false);
      }
    }
  }, [isNavigating, sessionId, targetSessionId, pathname, setNavigating]);

  if (!isNavigating) return null;

  return (
    <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 flex items-center justify-center">
    </div>
  );
}
