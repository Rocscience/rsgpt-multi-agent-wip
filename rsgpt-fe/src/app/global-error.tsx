'use client' // Error boundaries must be Client Components

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    // global-error must include html and body tags
    <html className="dark">
      <body className="bg-background text-foreground">
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 border">
            <h2 className="text-xl font-semibold text-foreground mb-4">Something went wrong!</h2>
            <p className="text-muted-foreground mb-6">
              A critical error has occurred. Please try refreshing the page. {error.message}
            </p>
            <button 
              onClick={() => reset()}
              className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground font-medium py-2 px-4 rounded-md transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}
