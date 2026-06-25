// app/providers.tsx
'use client'

import { HeroUIProvider } from '@heroui/react';
import { ThemeProvider } from 'next-themes';
import { Auth0Provider } from "@auth0/nextjs-auth0";
import { QueryClient, QueryClientProvider, MutationCache, QueryCache } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import * as Sentry from '@sentry/nextjs';
import { LogoutHandler } from '@/components/auth/logout-handler';
import { ThemeInitializer } from '@/components/ui/theme-initializer';
import { SentryUserSetter } from '@/components/sentry/sentry-user-setter';
import { SentryFeedbackWidget } from '@/components/sentry/sentry-feedback-widget';
import { GlobalAlertContainer } from '@/components/alerts/global-alert-container';
import { useGlobalAlerts, shouldSilenceError } from '@/hooks/useGlobalAlerts';
import { Analytics } from "@vercel/analytics/next"

// Helper to get user-friendly error message
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return 'An unexpected error occurred';
}

// Helper to get user-friendly error title based on error type
function getErrorTitle(error: unknown, isMutation: boolean): string {
  const message = getErrorMessage(error).toLowerCase();
  
  if (message.includes('timeout') || message.includes('abort')) {
    return 'Request Timed Out';
  }
  if (message.includes('not found') || message.includes('404')) {
    return 'Not Found';
  }
  if (message.includes('forbidden') || message.includes('403')) {
    return 'Access Denied';
  }
  if (message.includes('rate limit') || message.includes('429') || message.includes('quota')) {
    return 'Rate Limited';
  }
  if (message.includes('server') || message.includes('500')) {
    return 'Server Error';
  }
  
  return isMutation ? 'Action Failed' : 'Failed to Load Data';
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        // Global error handler for queries (data fetching)
        queryCache: new QueryCache({
          onError: (error, query) => {
            const errorMessage = getErrorMessage(error);
            
            // Skip if this query opted out of global error handling
            if (query.meta?.skipGlobalErrorHandler) {
              return;
            }
            
            // Skip silent errors (handled elsewhere)
            if (shouldSilenceError(errorMessage)) {
              return;
            }
            
            // Log to Sentry with context
            Sentry.captureException(error, {
              tags: { 
                errorType: 'query',
                queryKey: JSON.stringify(query.queryKey),
              },
            });
            
            // Query errors are typically less critical (data just stays stale)
            // Only show alert for queries that explicitly want it via meta
            if (query.meta?.showErrorAlert) {
              useGlobalAlerts.getState().showError(
                getErrorTitle(error, false),
                errorMessage
              );
            }
            
            console.error('[Query Error]', query.queryKey, error);
          },
        }),
        
        // Global error handler for mutations (actions like create, update, delete)
        mutationCache: new MutationCache({
          onError: (error, variables, context, mutation) => {
            const errorMessage = getErrorMessage(error);
            
            // Skip if this mutation opted out of global error handling
            if (mutation.meta?.skipGlobalErrorHandler) {
              return;
            }
            
            // Skip silent errors (handled elsewhere)
            if (shouldSilenceError(errorMessage)) {
              return;
            }
            
            // Log to Sentry with context
            Sentry.captureException(error, {
              tags: { 
                errorType: 'mutation',
                mutationKey: mutation.options.mutationKey 
                  ? JSON.stringify(mutation.options.mutationKey) 
                  : 'unnamed',
              },
              extra: { 
                variables: typeof variables === 'object' ? variables : { value: variables },
              },
            });
            
            // Mutation errors are more critical - show alert by default
            // Unless the mutation explicitly opts out
            if (mutation.meta?.skipErrorAlert !== true) {
              useGlobalAlerts.getState().showError(
                getErrorTitle(error, true),
                errorMessage
              );
            }
            
            console.error('[Mutation Error]', mutation.options.mutationKey, error);
          },
        }),
        
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 5,
            retry: 1,
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
            refetchOnMount: false,
            gcTime: 1000 * 60 * 60,
          },
        },
      })
  );

  useEffect(() => {
    // Provider mounted
    return () => {
      // Provider unmounted
    };
  }, []);

  return (
    <Auth0Provider>
      <HeroUIProvider>
        <ThemeProvider 
          attribute="class" 
          defaultTheme="system" 
          enableSystem
          storageKey="rsgpt-theme"
          disableTransitionOnChange={false}
        >
          <QueryClientProvider client={queryClient}>
            <ThemeInitializer />
            <LogoutHandler />
            <SentryUserSetter />
            <SentryFeedbackWidget />
            <GlobalAlertContainer />
            <Analytics />
            {children}
          </QueryClientProvider>
        </ThemeProvider>
      </HeroUIProvider>
    </Auth0Provider>
  );
}
