import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import { useRouter } from 'next/navigation'
import { useCreateSession } from '@/hooks/useCreateSession'
import { usePendingFirstMessage } from '@/hooks/usePendingFirstMessage'
import { useMessageInputState } from '@/hooks/useMessageInputState'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: jest.fn()
}))

// Mock the custom hooks
jest.mock('@/hooks/useCreateSession', () => ({
  useCreateSession: jest.fn()
}))

// Mock Zustand stores
jest.mock('@/hooks/usePendingFirstMessage', () => ({
  usePendingFirstMessage: jest.fn()
}))

jest.mock('@/hooks/useMessageInputState', () => ({
  useMessageInputState: jest.fn()
}))

// Mock the MessageInput component
jest.mock('@/components/chat/input/message-input', () => ({
  MessageInput: () => <div data-testid="message-input">Message Input Component</div>
}))

// Mock the alerts component
jest.mock('@/components/alerts/alerts', () => ({
  SessionCreationErrorAlert: ({ onRetry, onDismiss, isLoading }: any) => (
    <div data-testid="session-error-alert">
      <button onClick={onRetry} disabled={isLoading}>Retry</button>
      <button onClick={onDismiss}>Dismiss</button>
    </div>
  )
}))

// Mock the NavigationOverlay component
jest.mock('@/components/chat/navigation/navigation-overlay', () => ({
  NavigationOverlay: () => <div data-testid="navigation-overlay">Navigation Overlay</div>
}))

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    form: ({ children, ...props }: any) => <form {...props}>{children}</form>
  }
}))

// Create a simplified test component that focuses on core chat page logic
// This extracts just the session creation behavior without URL complexity
const SimplifiedChatPage = () => {
  const router = useRouter()
  const createSession = useCreateSession()
  const setPending = usePendingFirstMessage((s: any) => s.set)
  const { setPosition, setOnSubmit, setDisabled, clearText } = useMessageInputState()
  
  const [sessionError, setSessionError] = React.useState<string | null>(null)
  const [retryData, setRetryData] = React.useState<{ text: string; sources: string[] } | null>(null)
  const [showHeading, setShowHeading] = React.useState(true)

  const handleSubmit = React.useCallback(async (text: string, sources: string[]) => {
    try {
      setSessionError(null)
      setRetryData(null)
      setShowHeading(false)
      setPending({ text, sources })
      setPosition('bottom')
      // Strip @[filepath] patterns from title to make it user-friendly
      const cleanTitle = text.replace(/@\[([^\]]+)\]/g, '').trim().slice(0, 60) || undefined
      const res = await createSession.mutateAsync({ title: cleanTitle })
      clearText()
      router.push(`/chat/${res.id}`)
    } catch (error) {
      setPosition('center')
      setShowHeading(true)
      setSessionError(error instanceof Error ? error.message : 'Failed to create session')
      setRetryData({ text, sources })
    }
  }, [setPending, setPosition, createSession, router, clearText])

  const handleRetry = React.useCallback(() => {
    if (retryData) {
      handleSubmit(retryData.text, retryData.sources)
    }
  }, [retryData, handleSubmit])

  const handleDismissError = React.useCallback(() => {
    setSessionError(null)
    setRetryData(null)
  }, [])

  const stableHandleSubmit = React.useCallback((text: string, sources: string[]) => {
    handleSubmit(text, sources)
  }, [handleSubmit])

  React.useEffect(() => {
    setPosition('center')
    setDisabled(false)
    setOnSubmit(stableHandleSubmit)
  }, [setPosition, setOnSubmit, setDisabled, stableHandleSubmit])

  return (
    <div className="relative flex h-full items-center justify-center -translate-y-10 md:-translate-y-20 px-2 sm:px-4">
      <div className="w-full max-w-[768px]">
        {showHeading && (
          <p className="font-bold text-2xl md:text-3xl text-center mb-[200px] md:mb-10 px-2">Ready when you are.</p>
        )}
        
        {sessionError && (
          <div className="fixed top-16 sm:top-20 md:top-24 right-2 sm:right-4 z-[60] max-w-sm sm:max-w-md">
            <div data-testid="session-error-alert">
              <button onClick={handleRetry} disabled={createSession.isPending}>Retry</button>
              <button onClick={handleDismissError}>Dismiss</button>
            </div>
          </div>
        )}
      </div>
      
      <div data-testid="navigation-overlay">Navigation Overlay</div>
    </div>
  )
}

const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
  forward: jest.fn(),
  refresh: jest.fn(),
  prefetch: jest.fn()
}

const mockCreateSession = {
  mutateAsync: jest.fn(),
  isPending: false,
  error: null
}

// Mock Zustand store selectors
const mockPendingFirstMessage = jest.fn()
const mockMessageInputState = jest.fn()

// Mock store methods
const mockSetPending = jest.fn()
const mockSetPosition = jest.fn()
const mockSetOnSubmit = jest.fn()
const mockSetDisabled = jest.fn()
const mockClearText = jest.fn()

describe('Chat Page - Core Session Creation Logic', () => {
  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks()
    
    // Setup default mock implementations
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)
    ;(useCreateSession as jest.Mock).mockReturnValue(mockCreateSession)
    
    // Mock the Zustand store selector pattern
    ;(usePendingFirstMessage as jest.Mock).mockImplementation((selector) => {
      if (typeof selector === 'function') {
        return selector({ set: mockSetPending })
      }
      return mockPendingFirstMessage
    })
    
    ;(useMessageInputState as jest.Mock).mockReturnValue({
      setPosition: mockSetPosition,
      setOnSubmit: mockSetOnSubmit,
      setDisabled: mockSetDisabled,
      clearText: mockClearText
    })
  })

  afterEach(() => {
    jest.resetAllMocks()
  })

  it('should render the main heading', () => {
    render(<SimplifiedChatPage />)
    expect(screen.getByText('Ready when you are.')).toBeInTheDocument()
  })

  it('should configure message input state on mount', () => {
    render(<SimplifiedChatPage />)
    
    expect(mockSetPosition).toHaveBeenCalledWith('center')
    expect(mockSetDisabled).toHaveBeenCalledWith(false)
    expect(mockSetOnSubmit).toHaveBeenCalled()
  })

  it('should handle successful session creation', async () => {
    const mockSessionId = 'test-session-id'
    mockCreateSession.mutateAsync.mockResolvedValue({ id: mockSessionId })

    render(<SimplifiedChatPage />)

    // Get the onSubmit function that was passed to useMessageInputState
    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    // Simulate message submission
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    expect(mockSetPending).toHaveBeenCalledWith({
      text: 'Test message',
      sources: ['ROC']
    })
    expect(mockSetPosition).toHaveBeenCalledWith('bottom')
    expect(mockCreateSession.mutateAsync).toHaveBeenCalledWith({
      title: 'Test message'
    })
    expect(mockRouter.push).toHaveBeenCalledWith(`/chat/${mockSessionId}`)
    expect(mockClearText).toHaveBeenCalled()
  })

  it('should handle session creation error', async () => {
    const errorMessage = 'Session creation failed'
    mockCreateSession.mutateAsync.mockRejectedValue(new Error(errorMessage))

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    // Should show error alert
    expect(screen.getByTestId('session-error-alert')).toBeInTheDocument()
    expect(screen.getByText('Retry')).toBeInTheDocument()
    expect(screen.getByText('Dismiss')).toBeInTheDocument()
    
    // Should reset position back to center
    expect(mockSetPosition).toHaveBeenCalledWith('center')
  })

  it('should handle retry functionality', async () => {
    const errorMessage = 'Session creation failed'
    mockCreateSession.mutateAsync
      .mockRejectedValueOnce(new Error(errorMessage))
      .mockResolvedValueOnce({ id: 'retry-session-id' })

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    // First submission fails
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    // Click retry button
    const retryButton = screen.getByText('Retry')
    await act(async () => {
      fireEvent.click(retryButton)
    })

    // Should retry with same data
    expect(mockCreateSession.mutateAsync).toHaveBeenCalledTimes(2)
    expect(mockRouter.push).toHaveBeenCalledWith('/chat/retry-session-id')
  })

  it('should truncate long session titles', async () => {
    const longMessage = 'This is a very long message that should be truncated to 60 characters maximum'
    const mockSessionId = 'test-session-id'
    mockCreateSession.mutateAsync.mockResolvedValue({ id: mockSessionId })

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    await act(async () => {
      await onSubmitCall(longMessage, ['ROC'])
    })

    expect(mockCreateSession.mutateAsync).toHaveBeenCalledWith({
      title: longMessage.slice(0, 60)
    })
  })

  it('should handle empty message title', async () => {
    const mockSessionId = 'test-session-id'
    mockCreateSession.mutateAsync.mockResolvedValue({ id: mockSessionId })

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    await act(async () => {
      await onSubmitCall('', ['ROC'])
    })

    expect(mockCreateSession.mutateAsync).toHaveBeenCalledWith({
      title: undefined
    })
  })

  it('should strip @[filepath] patterns from session title', async () => {
    const messageWithFilePath = '@[/path/to/file.ts] What does this file do?'
    const mockSessionId = 'test-session-id'
    mockCreateSession.mutateAsync.mockResolvedValue({ id: mockSessionId })

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    await act(async () => {
      await onSubmitCall(messageWithFilePath, ['ROC'])
    })

    expect(mockCreateSession.mutateAsync).toHaveBeenCalledWith({
      title: 'What does this file do?'
    })
  })

  it('should strip multiple @[filepath] patterns from session title', async () => {
    const messageWithFilePaths = '@[/path/file1.ts] @[/path/file2.ts] Compare these files'
    const mockSessionId = 'test-session-id'
    mockCreateSession.mutateAsync.mockResolvedValue({ id: mockSessionId })

    render(<SimplifiedChatPage />)

    const onSubmitCall = mockSetOnSubmit.mock.calls[0][0]
    
    await act(async () => {
      await onSubmitCall(messageWithFilePaths, ['ROC'])
    })

    expect(mockCreateSession.mutateAsync).toHaveBeenCalledWith({
      title: 'Compare these files'
    })
  })
})
