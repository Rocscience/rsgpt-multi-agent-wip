import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex items-center justify-center h-full bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 text-center border">
        <h2 className="text-xl font-bold text-foreground mb-4">Session Not Found</h2>
        <p className="text-muted-foreground mb-6">
          This chat session does not exist or may have been deleted.
        </p>
        <div className="space-y-3">
          <Link 
            href="/chat"
            className="block w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-md transition-colors text-center"
          >
            Start New Chat
          </Link>
          <Link 
            href="/"
            className="block w-full bg-secondary hover:bg-secondary/90 text-secondary-foreground font-medium py-2 px-4 rounded-md transition-colors text-center"
          >
            Return Home
          </Link>
        </div>
      </div>
    </div>
  )
}
