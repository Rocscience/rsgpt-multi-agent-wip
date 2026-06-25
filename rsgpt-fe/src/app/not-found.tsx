import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-md w-full bg-card rounded-lg shadow-md p-6 text-center border">
        <h2 className="text-2xl font-bold text-foreground mb-4">404 - Page Not Found</h2>
        <p className="text-muted-foreground mb-6">
          The page you are looking for does not exist.
        </p>
        <Link 
          href="/"
          className="inline-block w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-2 px-4 rounded-md transition-colors"
        >
          Return Home
        </Link>
      </div>
    </div>
  )
}
