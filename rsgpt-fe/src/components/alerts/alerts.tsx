'use client'

import { Alert, Button, Link } from "@heroui/react";

// Portal Account Alert
// Displays a warning if the user's portal account is missing information and provides a link to the portal
export function PortalAccountAlert({ onRetry, isLoading }: { onRetry?: () => void; isLoading?: boolean }) {
    return (
        <Alert 
            color="warning" 
            variant="faded"
            title="Your account is missing information"
            description="Please complete your portal account information to continue."
            endContent={
                <div className="flex gap-2">
                    {onRetry && (
                        <Button 
                            onClick={onRetry} 
                            variant="bordered" 
                            color="warning" 
                            size="sm"
                            isLoading={isLoading}
                        >
                            Retry
                        </Button>
                    )}
                    <Button as={Link} href="https://www.rocscience.com/portal" target="_blank" variant="solid" color="warning" size="sm">
                        Go to RocPortal
                    </Button>
                </div>
            }
            >
        </Alert>
    )
}

// Session Creation Error Alert
// Displays an error when session creation fails and allows retry
export function SessionCreationErrorAlert({ onRetry, onDismiss, isLoading }: { 
    onRetry: () => void; 
    onDismiss: () => void; 
    isLoading?: boolean 
}) {
    return (
        <Alert 
            color="danger" 
            variant="faded"
            title="Failed to create session"
            description="We couldn't create your chat session. Please try again."
            isClosable
            onClose={onDismiss}
            endContent={
                <Button 
                    onClick={onRetry} 
                    variant="bordered" 
                    color="danger" 
                    size="sm"
                    isLoading={isLoading}
                >
                    Retry
                </Button>
            }
            >
        </Alert>
    )
}

// Streaming Error Alert
// Displays an error when message streaming fails and allows retry
export function StreamingErrorAlert({ onRetry, onDismiss, isLoading }: { 
    onRetry: () => void; 
    onDismiss: () => void; 
    isLoading?: boolean 
}) {
    return (
        <Alert 
            color="danger" 
            variant="faded"
            title="Failed to send message"
            description="We couldn't send your message. Please try again."
            isClosable
            onClose={onDismiss}
            endContent={
                <Button 
                    onClick={onRetry} 
                    variant="bordered" 
                    color="danger" 
                    size="sm"
                    isLoading={isLoading}
                >
                    Retry
                </Button>
            }
            >
        </Alert>
    )
}

// Account Setup Alert
// Displays when user's account is not properly linked to an organization
export function AccountSetupAlert({ onRetry, isLoading }: { onRetry?: () => void; isLoading?: boolean }) {
    return (
        <Alert 
            color="danger" 
            variant="faded"
            title="Account setup incomplete"
            description="Your account is not linked to an organization. Please contact support or check your RocPortal account."
            endContent={
                <div className="flex gap-2">
                    {onRetry && (
                        <Button 
                            onClick={onRetry} 
                            variant="bordered" 
                            color="danger" 
                            size="sm"
                            isLoading={isLoading}
                        >
                            Retry
                        </Button>
                    )}
                    <Button as={Link} href="https://www.rocscience.com/portal" target="_blank" variant="solid" color="danger" size="sm">
                        Go to RocPortal
                    </Button>
                </div>
            }
            >
        </Alert>
    )
}

// Network Interruption Alert
// Displays when streaming is interrupted due to network loss
export function NetworkInterruptionAlert({ onRetry, onDismiss, isLoading, isOnline }: { 
    onRetry: () => void; 
    onDismiss: () => void; 
    isLoading?: boolean;
    isOnline?: boolean;
}) {
    return (
        <Alert 
            color="warning" 
            variant="faded"
            title="Connection lost during response"
            description={isOnline 
                ? "Your network connection was interrupted. You can retry your message now."
                : "You're currently offline. The retry will be attempted when you're back online."
            }
            isClosable
            onClose={onDismiss}
            endContent={
                <Button 
                    onClick={onRetry} 
                    variant="bordered" 
                    color="warning" 
                    size="sm"
                    isLoading={isLoading}
                    isDisabled={!isOnline}
                >
                    {isOnline ? 'Retry' : 'Waiting...'}
                </Button>
            }
        />
    )
}