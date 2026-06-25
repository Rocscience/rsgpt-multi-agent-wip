'use client' // Error boundaries must be Client Components

import { useEffect } from 'react'
import Link from 'next/link'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Session error:', error)
  }, [error])

  return (
    <div className="flex items-center justify-center h-full bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 border">
        <h2 className="text-xl font-semibold text-foreground mb-4">Session Error</h2>
        <p className="text-muted-foreground mb-6">
          Something went wrong loading this chat session. The session may be corrupted or unavailable.
        </p>
        <div className="space-y-3">
          <button
            onClick={() => reset()}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-md transition-colors"
          >
            Try again
          </button>
          <Link
            href="/chat"
            className="block w-full text-center bg-secondary hover:bg-secondary/90 text-secondary-foreground font-medium py-2 px-4 rounded-md transition-colors"
          >
            Start New Chat
          </Link>
        </div>
      </div>
    </div>
  )
}
