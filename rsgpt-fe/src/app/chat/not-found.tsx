import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex items-center justify-center h-full bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 text-center border">
        <h2 className="text-xl font-bold text-foreground mb-4">Chat Not Found</h2>
        <p className="text-muted-foreground mb-6">
          The chat session you are looking for does not exist.
        </p>
        <div className="flex gap-3">
          <Link 
            href="/chat"
            className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-md transition-colors text-center"
          >
            New Chat
          </Link>
          <Link 
            href="/"
            className="flex-1 bg-secondary hover:bg-secondary/90 text-secondary-foreground font-medium py-2 px-4 rounded-md transition-colors text-center"
          >
            Home
          </Link>
        </div>
      </div>
    </div>
  )
}
