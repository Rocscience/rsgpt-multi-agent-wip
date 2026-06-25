'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { Button, Tooltip } from '@heroui/react';
import { FlagIcon } from '@heroicons/react/24/outline';

/**
 * Manages the Sentry feedback widget with a custom trigger button.
 * Position: top-right on chat pages, bottom-right on dashboard/main page.
 * Theme is controlled via CSS in globals.css based on the .dark class.
 */
export function SentryFeedbackWidget() {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const pathname = usePathname();
  
  // Determine if we're on a chat page
  const isChatPage = pathname?.startsWith('/chat');

  useEffect(() => {
    const feedback = Sentry.getFeedback();
    if (!feedback || !buttonRef.current) return;

    // Attach the feedback form to our custom button
    const unsubscribe = feedback.attachTo(buttonRef.current, {
      formTitle: 'Report an Issue',
    });
    unsubscribeRef.current = unsubscribe;

    return () => {
      if (unsubscribeRef.current) {
        try {
          unsubscribeRef.current();
        } catch (e) {
          // Cleanup might fail if already removed
        }
        unsubscribeRef.current = null;
      }
    };
  }, []);

  return (
    <div 
      className={`fixed z-50 ${
        isChatPage 
          ? 'top-3 right-3' 
          : 'bottom-3 right-3'
      }`}
    >
      <Tooltip content="Report an Issue" placement={isChatPage ? 'bottom' : 'top'}>
        <Button
          ref={buttonRef}
          isIconOnly
          variant="flat"
          color="default"
          aria-label="Report an Issue"
          className="bg-content1 hover:bg-default-100 shadow-md border border-default-200"
        >
          <FlagIcon className="w-5 h-5 text-foreground" />
        </Button>
      </Tooltip>
    </div>
  );
}
