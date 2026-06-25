'use client';

import { useEffect, useState } from 'react';
import { Alert } from '@heroui/react';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

export function OfflineAlert() {
  const { isOnline, wasOffline, clearWasOffline, queuedActions, suppressOfflineAlert } = useNetworkStatus();
  const [showReconnectedAlert, setShowReconnectedAlert] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  // Prevent hydration mismatch by only rendering after mount
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Handle showing "Back Online" alert when reconnecting
  useEffect(() => {
    if (wasOffline && isOnline) {
      setShowReconnectedAlert(true);
      
      // Auto-hide the reconnected alert after 3 seconds
      const timeout = setTimeout(() => {
        setShowReconnectedAlert(false);
        clearWasOffline();
      }, 3000);
      
      return () => clearTimeout(timeout);
    }
  }, [wasOffline, isOnline, clearWasOffline]);

  // Don't render anything during SSR to prevent hydration mismatch
  if (!isMounted) {
    return null;
  }
  
  // Don't show if suppressed (stream-specific error is being shown)
  if (suppressOfflineAlert) {
    return null;
  }

  // Show offline alert when offline
  if (!isOnline) {
    return (
      <div className="fixed top-4 right-4 z-50 max-w-md">
        <Alert
          color="warning"
          variant="flat"
          title="You're Offline"
          description={
            queuedActions.length > 0
              ? `No internet connection. ${queuedActions.length} action${queuedActions.length > 1 ? 's' : ''} will retry when you're back online.`
              : "No internet connection. Some features may not work until you're back online."
          }
        />
      </div>
    );
  }

  // Show "Back Online" alert briefly when reconnecting
  if (showReconnectedAlert) {
    return (
      <div className="fixed top-4 right-4 z-50 max-w-md">
        <Alert
          color="success"
          variant="flat"
          title="Back Online"
          description={
            queuedActions.length > 0
              ? `Connection restored. Retrying ${queuedActions.length} queued action${queuedActions.length > 1 ? 's' : ''}...`
              : "Your internet connection has been restored."
          }
          isClosable
          onClose={() => {
            setShowReconnectedAlert(false);
            clearWasOffline();
          }}
        />
      </div>
    );
  }

  return null;
}
