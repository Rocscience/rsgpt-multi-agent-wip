'use client' // Error boundaries must be Client Components

import { useEffect } from 'react'
import { Button } from '@heroui/react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(error)
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 border">
        <h2 className="text-xl font-semibold text-foreground mb-4">Something went wrong!</h2>
        <p className="text-muted-foreground mb-6">
          An unexpected error has occurred. Please try again or contact support if the problem persists.
        </p>
        <Button
          onPress={() => reset()}
          color="primary"
          className="w-full"
        >
          Try again
        </Button>
      </div>
    </div>
  )
}
