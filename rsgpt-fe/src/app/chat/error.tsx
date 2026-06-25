'use client' // Error boundaries must be Client Components

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Chat error:', error)
  }, [error])

  return (
    <div className="flex items-center justify-center h-full bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 border">
        <h2 className="text-xl font-semibold text-foreground mb-4">Chat Error</h2>
        <p className="text-muted-foreground mb-6">
          Something went wrong with the chat functionality. Please try again.
        </p>
        <button
          onClick={() => reset()}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-md transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  )
}
