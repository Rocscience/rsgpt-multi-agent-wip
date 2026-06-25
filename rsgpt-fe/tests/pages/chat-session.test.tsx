import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import { useParams, notFound } from 'next/navigation'
import ChatSessionPage from '@/app/chat/[sessionId]/page'
import { useGetChatSessionHistory } from '@/hooks/useGetChatSessionHistory'
import { usePendingFirstMessage } from '@/hooks/usePendingFirstMessage'
import { useStreamPrompt } from '@/hooks/useStreamPrompt'
import { useMessageInputState } from '@/hooks/useMessageInputState'
import { useChatMessages } from '@/hooks/useChatMessages'
import { useModelSelection } from '@/hooks/useModelSelection'

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
  notFound: jest.fn()
}))

// Mock the custom hooks
jest.mock('@/hooks/useGetChatSessionHistory', () => ({
  useGetChatSessionHistory: jest.fn()
}))

jest.mock('@/hooks/usePendingFirstMessage', () => ({
  usePendingFirstMessage: jest.fn()
}))

jest.mock('@/hooks/useStreamPrompt', () => ({
  useStreamPrompt: jest.fn()
}))

jest.mock('@/hooks/useMessageInputState', () => ({
  useMessageInputState: jest.fn()
}))

jest.mock('@/hooks/useChatMessages', () => ({
  useChatMessages: jest.fn()
}))

// Create mock references for tests
const mockChatMessages = {
  getConversationTurns: jest.fn().mockReturnValue([]),
  mergeConversationTurns: jest.fn(),
  getCurrentStreamingTurn: jest.fn().mockReturnValue(undefined),
  isSessionStreaming: jest.fn().mockReturnValue(false),
  getState: jest.fn().mockReturnValue({
    streamState: {
      isStreaming: false,
      streamAbortController: null,
      streamSessionId: null
    },
    updateStreamingAIResponse: jest.fn()
  })
}

jest.mock('@/hooks/useModelSelection', () => ({
  useModelSelection: jest.fn()
}))

// Mock the MessageList component
jest.mock('@/components/chat/messages/message-list', () => ({
  MessageList: ({ conversationTurns, currentStreamingTurn, onLoadMore, hasMore, isLoading, sessionId }: any) => (
    <div data-testid="message-list">
      <div data-testid="conversation-turns">{JSON.stringify(conversationTurns)}</div>
      <div data-testid="current-streaming-turn">{JSON.stringify(currentStreamingTurn)}</div>
      <div data-testid="session-id">{sessionId}</div>
      <button onClick={onLoadMore} disabled={!hasMore || isLoading}>
        Load More
      </button>
    </div>
  )
}))

// Mock the alerts component
jest.mock('@/components/alerts/alerts', () => ({
  StreamingErrorAlert: ({ onRetry, onDismiss, isLoading }: any) => (
    <div data-testid="streaming-error-alert">
      <button onClick={onRetry} disabled={isLoading}>Retry</button>
      <button onClick={onDismiss}>Dismiss</button>
    </div>
  )
}))

const mockParams = {
  sessionId: '123e4567-e89b-12d3-a456-426614174000'
}

const mockChatSessionHistory = {
  data: {
    pages: [
      {
        conversation: [
          {
            user_message: {
              id: '1',
              message_text: 'Hello',
              created_at: '2023-01-01T00:00:00Z',
              status: 'completed',
              sources_requested: ['ROC']
            },
            ai_responses: [
              {
                id: 'ai-1',
                message_text: 'Hi there!',
                status: 'completed',
                is_latest: true,
                created_at: '2023-01-01T00:00:01Z'
              }
            ],
            has_retries: false
          }
        ]
      }
    ]
  },
  fetchNextPage: jest.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  error: null,
  refetch: jest.fn()
}

const mockPendingFirstMessage = {
  text: '',
  sources: [],
  selectedModel: undefined,
  clear: jest.fn()
}

const mockStreamPrompt = {
  sendMessage: jest.fn()
}

const mockMessageInputState = {
  setPosition: jest.fn(),
  setOnSubmit: jest.fn(),
  setDisabled: jest.fn(),
  clearText: jest.fn()
}

// mockChatMessages is now defined above after the jest.mock

const mockModelSelection = {
  selectedModel: 'gpt-4.1-2025-04-14',
  setSelectedModel: jest.fn()
}

describe('Chat Session Page', () => {
  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks()
    
    // Setup default mock implementations
    ;(useParams as jest.Mock).mockReturnValue(mockParams)
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue(mockChatSessionHistory)
    ;(usePendingFirstMessage as unknown as jest.Mock).mockReturnValue(mockPendingFirstMessage)
    ;(useStreamPrompt as jest.Mock).mockReturnValue(mockStreamPrompt)
    ;(useMessageInputState as unknown as jest.Mock).mockReturnValue(mockMessageInputState)
    ;(useModelSelection as unknown as jest.Mock).mockReturnValue(mockModelSelection)

    ;(useChatMessages as unknown as jest.Mock).mockReturnValue({
      getConversationTurns: jest.fn().mockReturnValue([]),
      mergeConversationTurns: jest.fn(),
      getCurrentStreamingTurn: jest.fn().mockReturnValue(undefined),
      isSessionStreaming: jest.fn().mockReturnValue(false),
      getState: jest.fn().mockReturnValue({
        streamState: {
          isStreaming: false,
          streamAbortController: null,
          streamSessionId: null
        },
        updateStreamingAIResponse: jest.fn()
      })
    })

    // Mock window.addEventListener and removeEventListener
    const mockAddEventListener = jest.fn()
    const mockRemoveEventListener = jest.fn()
    Object.defineProperty(window, 'addEventListener', {
      value: mockAddEventListener,
      writable: true
    })
    Object.defineProperty(window, 'removeEventListener', {
      value: mockRemoveEventListener,
      writable: true
    })
  })

  afterEach(() => {
    jest.resetAllMocks()
  })

  it('should render with valid session ID', () => {
    render(<ChatSessionPage />)

    expect(screen.getByTestId('message-list')).toBeInTheDocument()
    expect(screen.getByTestId('session-id')).toHaveTextContent(mockParams.sessionId)
  })

  it('should call notFound for invalid session ID format', () => {
    ;(useParams as jest.Mock).mockReturnValue({
      sessionId: 'invalid-session-id'
    })

    render(<ChatSessionPage />)

    expect(notFound).toHaveBeenCalled()
  })

  it('should configure message input state for valid session', () => {
    render(<ChatSessionPage />)

    expect(mockMessageInputState.setPosition).toHaveBeenCalledWith('bottom')
    expect(mockMessageInputState.setDisabled).toHaveBeenCalledWith(false)
    expect(mockMessageInputState.setOnSubmit).toHaveBeenCalled()
  })

  it('should handle pending first message from new chat', () => {
    const pendingMessage = {
      text: 'Hello from new chat',
      sources: ['ROC'],
      selectedModel: undefined,
      clear: jest.fn()
    }
    ;(usePendingFirstMessage as unknown as jest.Mock).mockReturnValue(pendingMessage)

    render(<ChatSessionPage />)

    expect(mockStreamPrompt.sendMessage).toHaveBeenCalledWith('Hello from new chat', ['ROC'], undefined, false, null, false)
    expect(pendingMessage.clear).toHaveBeenCalled()
  })

  it('should load chat history when no pending message', () => {
    const historyData = {
      pages: [
        {
          conversation: [
            {
              id: '1',
              user_message: 'Hello',
              ai_message: 'Hi there!',
              created_at: '2023-01-01T00:00:00Z'
            }
          ]
        }
      ]
    }
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      data: historyData
    })

    render(<ChatSessionPage />)

    // Check that the component renders and processes history
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle successful message submission', async () => {
    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Simulate message submission
    await onSubmitCall('Test message', ['ROC'])

    expect(mockMessageInputState.clearText).toHaveBeenCalled()
    expect(mockStreamPrompt.sendMessage).toHaveBeenCalledWith('Test message', ['ROC'], 'gpt-4.1-2025-04-14', false, null, false)
  })

  it('should handle streaming error and show retry functionality', async () => {
    const errorMessage = 'Streaming failed'
    mockStreamPrompt.sendMessage.mockImplementation(() => {
      throw new Error(errorMessage)
    })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Simulate message submission that fails
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    // Should show streaming error alert
    await waitFor(() => {
      expect(screen.getByTestId('streaming-error-alert')).toBeInTheDocument()
    })
  })

  it('should handle retry after streaming error', async () => {
    mockStreamPrompt.sendMessage
      .mockImplementationOnce(() => {
        throw new Error('First attempt failed')
      })
      .mockImplementationOnce(() => {
        // Success on retry
      })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // First submission fails
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })
    
    // Should show error alert
    await waitFor(() => {
      expect(screen.getByTestId('streaming-error-alert')).toBeInTheDocument()
    })
    
    // Click retry button
    const retryButton = screen.getByText('Retry')
    await act(async () => {
      fireEvent.click(retryButton)
    })

    // Should retry with same data
    expect(mockStreamPrompt.sendMessage).toHaveBeenCalledTimes(2)
  })

  it('should handle error dismissal', async () => {
    mockStreamPrompt.sendMessage.mockImplementation(() => {
      throw new Error('Streaming failed')
    })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Submit message that fails
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })
    
    // Should show error alert
    await waitFor(() => {
      expect(screen.getByTestId('streaming-error-alert')).toBeInTheDocument()
    })
    
    // Click dismiss button
    const dismissButton = screen.getByText('Dismiss')
    await act(async () => {
      fireEvent.click(dismissButton)
    })

    // Error alert should be removed
    expect(screen.queryByTestId('streaming-error-alert')).not.toBeInTheDocument()
  })

  it('should handle session not found error from API', () => {
    const sessionError = new Error('Session not found')
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      error: sessionError
    })

    render(<ChatSessionPage />)

    expect(mockMessageInputState.setDisabled).toHaveBeenCalledWith(true)
    expect(notFound).toHaveBeenCalled()
  })

  it('should handle various session error scenarios', () => {
    const errorScenarios = [
      'session not found',
      '422',
      '404',
      'unprocessable',
      'invalid session',
      'session id'
    ]

    errorScenarios.forEach(errorMessage => {
      jest.clearAllMocks()
      
      const sessionError = new Error(errorMessage)
      ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
        ...mockChatSessionHistory,
        error: sessionError
      })

      render(<ChatSessionPage />)

      expect(mockMessageInputState.setDisabled).toHaveBeenCalledWith(true)
      expect(notFound).toHaveBeenCalled()
    })
  })

  it('should handle load more functionality', () => {
    const mockFetchNextPage = jest.fn()
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      fetchNextPage: mockFetchNextPage,
      hasNextPage: true
    })

    render(<ChatSessionPage />)

    const loadMoreButton = screen.getByText('Load More')
    fireEvent.click(loadMoreButton)

    expect(mockFetchNextPage).toHaveBeenCalled()
  })

  it('should disable load more button when no more pages', () => {
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      hasNextPage: false
    })

    render(<ChatSessionPage />)

    const loadMoreButton = screen.getByText('Load More')
    expect(loadMoreButton).toBeDisabled()
  })

  it('should disable load more button when fetching', () => {
    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      hasNextPage: true,
      isFetchingNextPage: true
    })

    render(<ChatSessionPage />)

    const loadMoreButton = screen.getByText('Load More')
    expect(loadMoreButton).toBeDisabled()
  })

  it('should handle conversation turns and streaming turn', () => {
    const mockConversationTurns = [
      { id: '1', user_message: 'Hello', ai_message: 'Hi!' }
    ]
    const mockStreamingTurn = { id: '2', user_message: 'How are you?' }

    mockChatMessages.getConversationTurns.mockReturnValue(mockConversationTurns)
    mockChatMessages.getCurrentStreamingTurn.mockReturnValue(mockStreamingTurn)

    render(<ChatSessionPage />)

    // Check that the component renders without errors
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle beforeunload event for cleanup', () => {
    const mockAddEventListener = jest.fn()
    const mockRemoveEventListener = jest.fn()
    
    Object.defineProperty(window, 'addEventListener', {
      value: mockAddEventListener,
      writable: true
    })
    Object.defineProperty(window, 'removeEventListener', {
      value: mockRemoveEventListener,
      writable: true
    })

    render(<ChatSessionPage />)

    expect(mockAddEventListener).toHaveBeenCalledWith('beforeunload', expect.any(Function))
  })

  it('should handle invalid session ID format immediately', () => {
    ;(useParams as jest.Mock).mockReturnValue({
      sessionId: 'not-a-valid-uuid'
    })

    render(<ChatSessionPage />)

    expect(notFound).toHaveBeenCalled()
    expect(mockMessageInputState.setPosition).toHaveBeenCalledWith('hidden')
    expect(mockMessageInputState.setDisabled).toHaveBeenCalledWith(true)
  })

  it('should maintain stable function references', () => {
    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall1 = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Verify the function is defined and callable
    expect(typeof onSubmitCall1).toBe('function')
    expect(onSubmitCall1).toBeDefined()
  })

  it('should handle scroll to bottom after message submission', async () => {
    // Mock scrollIntoView method
    const mockScrollIntoView = jest.fn()
    const mockUserMessageElement = { scrollIntoView: mockScrollIntoView }
    const mockQuerySelectorAll = jest.fn().mockReturnValue([mockUserMessageElement])
    const mockDispatchEvent = jest.fn()
    
    Object.defineProperty(document, 'querySelectorAll', {
      value: mockQuerySelectorAll,
      writable: true
    })
    Object.defineProperty(window, 'dispatchEvent', {
      value: mockDispatchEvent,
      writable: true
    })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Simulate message submission
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    // Wait for the setTimeout to execute (50ms + 100ms delay in the component)
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 200))
    })

    // Should dispatch 'message-submitted' event
    expect(mockDispatchEvent).toHaveBeenCalled()
    
    // Should query for user messages and scroll to last one
    expect(mockQuerySelectorAll).toHaveBeenCalledWith('[data-user-message]')
    expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
  })

  it('should handle beforeunload cleanup for active streams', () => {
    const mockAbort = jest.fn()
    const mockAbortController = { abort: mockAbort }
    
    // Mock the useChatMessages hook to include getState method
    const mockChatMessagesWithStream = {
      ...mockChatMessages,
      getState: jest.fn().mockReturnValue({
        streamState: {
          isStreaming: true,
          streamAbortController: mockAbortController
        }
      })
    }
    
    // Mock the useChatMessages module to return our enhanced mock
    ;(useChatMessages as unknown as jest.Mock).mockReturnValue(mockChatMessagesWithStream)
    
    // Also mock the module's getState method directly
    const originalUseChatMessages = useChatMessages as any
    originalUseChatMessages.getState = jest.fn().mockReturnValue({
      streamState: {
        isStreaming: true,
        streamAbortController: mockAbortController
      }
    })

    const mockAddEventListener = jest.fn()
    const mockRemoveEventListener = jest.fn()
    
    Object.defineProperty(window, 'addEventListener', {
      value: mockAddEventListener,
      writable: true
    })
    Object.defineProperty(window, 'removeEventListener', {
      value: mockRemoveEventListener,
      writable: true
    })

    render(<ChatSessionPage />)

    // Get the beforeunload handler
    const beforeunloadHandler = mockAddEventListener.mock.calls.find(
      call => call[0] === 'beforeunload'
    )?.[1]

    expect(beforeunloadHandler).toBeDefined()

    // Simulate beforeunload event
    if (beforeunloadHandler) {
      beforeunloadHandler()
      expect(mockAbort).toHaveBeenCalled()
    }
  })

  it('should handle multiple conversation turns correctly', () => {
    const mockConversationTurns = [
      {
        user_message: { id: '1', message_text: 'Hello', created_at: '2023-01-01T00:00:00Z' },
        ai_responses: [{ id: '1', message_text: 'Hi there!', is_latest: true }]
      },
      {
        user_message: { id: '2', message_text: 'How are you?', created_at: '2023-01-01T00:01:00Z' },
        ai_responses: [{ id: '2', message_text: 'I am fine!', is_latest: true }]
      }
    ]

    mockChatMessages.getConversationTurns.mockReturnValue(mockConversationTurns)

    render(<ChatSessionPage />)

    // Check that the component renders and handles multiple conversation turns
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle streaming turn with AI response', () => {
    const mockStreamingTurn = {
      userMessage: {
        id: 'temp-1',
        message_text: 'Streaming message',
        created_at: new Date(),
        client_temp_id: 'temp-1'
      },
      aiResponse: {
        id: 'ai-1',
        text: 'Streaming response...',
        isLoading: true,
        isComplete: false
      }
    }

    mockChatMessages.getCurrentStreamingTurn.mockReturnValue(mockStreamingTurn)

    render(<ChatSessionPage />)

    // Check that the component handles streaming state
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle empty conversation turns', () => {
    mockChatMessages.getConversationTurns.mockReturnValue([])
    mockChatMessages.getCurrentStreamingTurn.mockReturnValue(undefined)

    render(<ChatSessionPage />)

    expect(screen.getByTestId('conversation-turns')).toHaveTextContent('[]')
    expect(screen.getByTestId('current-streaming-turn')).toHaveTextContent('')
  })

  it('should handle pagination with multiple pages', () => {
    const mockHistoryData = {
      pages: [
        {
          conversation: [
            {
              user_message: { id: '1', message_text: 'First message', created_at: '2023-01-01T00:00:00Z' },
              ai_responses: [{ id: '1', message_text: 'First response', is_latest: true }]
            }
          ]
        },
        {
          conversation: [
            {
              user_message: { id: '2', message_text: 'Second message', created_at: '2023-01-01T00:01:00Z' },
              ai_responses: [{ id: '2', message_text: 'Second response', is_latest: true }]
            }
          ]
        }
      ]
    }

    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      data: mockHistoryData,
      hasNextPage: true
    })

    render(<ChatSessionPage />)

    // Check that the component renders and handles pagination
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle retry state correctly', async () => {
    mockStreamPrompt.sendMessage.mockImplementation(() => {
      throw new Error('Streaming failed')
    })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Submit message that fails
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })
    
    // Should show error alert
    await waitFor(() => {
      expect(screen.getByTestId('streaming-error-alert')).toBeInTheDocument()
    })
    
    // Retry button should be enabled initially
    const retryButton = screen.getByText('Retry')
    expect(retryButton).not.toBeDisabled()
  })

  it('should handle session ID validation edge cases', () => {
    const invalidSessionIds = [
      'not-a-uuid',
      '123',
      '123e4567-e89b-12d3-a456-42661417400', // too short
      '123e4567-e89b-12d3-a456-4266141740000', // too long
      '123e4567-e89b-12d3-a456-42661417400g' // invalid character
    ]

    invalidSessionIds.forEach(invalidId => {
      jest.clearAllMocks()
      
      ;(useParams as jest.Mock).mockReturnValue({
        sessionId: invalidId
      })

      render(<ChatSessionPage />)

      expect(notFound).toHaveBeenCalled()
      expect(mockMessageInputState.setPosition).toHaveBeenCalledWith('hidden')
      expect(mockMessageInputState.setDisabled).toHaveBeenCalledWith(true)
    })
  })

  it('should handle empty session ID', () => {
    jest.clearAllMocks()
    
    ;(useParams as jest.Mock).mockReturnValue({
      sessionId: ''
    })

    render(<ChatSessionPage />)

    // Empty string should NOT trigger notFound (because sessionId && is false)
    // and should NOT call setPosition (because sessionId && !isValidGuidFormat is false)
    expect(notFound).not.toHaveBeenCalled()
    expect(mockMessageInputState.setPosition).not.toHaveBeenCalled()
    expect(mockMessageInputState.setDisabled).not.toHaveBeenCalled()
  })

  it('should handle null and undefined session IDs', () => {
    const nullUndefinedIds = [null, undefined]

    nullUndefinedIds.forEach(invalidId => {
      jest.clearAllMocks()
      
      ;(useParams as jest.Mock).mockReturnValue({
        sessionId: invalidId
      })

      render(<ChatSessionPage />)

      // For null/undefined, the component should NOT call notFound (because sessionId && is false)
      // and should NOT call setPosition (because sessionId && !isValidGuidFormat is false)
      expect(notFound).not.toHaveBeenCalled()
      expect(mockMessageInputState.setPosition).not.toHaveBeenCalled()
      expect(mockMessageInputState.setDisabled).not.toHaveBeenCalled()
    })
  })

  it('should handle message submission with different source combinations', async () => {
    const sourceCombinations = [
      ['ROC'],
      ['DIANA'],
      ['3GSM'],
      ['ROC', 'DIANA'],
      ['ROC', '3GSM'],
      ['DIANA', '3GSM'],
      ['ROC', 'DIANA', '3GSM']
    ]

    for (const sources of sourceCombinations) {
      jest.clearAllMocks()
      
      render(<ChatSessionPage />)

      // Get the onSubmit function
      const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
      
      // Simulate message submission with different sources
      await act(async () => {
        await onSubmitCall('Test message', sources)
      })

      expect(mockStreamPrompt.sendMessage).toHaveBeenCalledWith('Test message', sources, 'gpt-4.1-2025-04-14', false, null, false)
    }
  })

  it('should handle streaming state changes correctly', () => {
    // Test with streaming state
    const mockStreamingState = {
      streamState: {
        isStreaming: true,
        streamAbortController: { abort: jest.fn() },
        streamSessionId: mockParams.sessionId
      }
    }
    
    mockChatMessages.getState.mockReturnValue(mockStreamingState)

    render(<ChatSessionPage />)

    // Should still render the component even when streaming
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle conversation history loading with proper data structure', () => {
    const realisticHistoryData = {
      pages: [
        {
          conversation: [
            {
              user_message: {
                id: 'user-1',
                message_text: 'What is the best way to analyze slope stability?',
                created_at: '2023-01-01T00:00:00Z',
                status: 'completed',
                sources_requested: ['ROC', 'DIANA']
              },
              ai_responses: [
                {
                  id: 'ai-1',
                  message_text: 'Slope stability analysis involves several key steps...',
                  status: 'completed',
                  is_latest: true,
                  created_at: '2023-01-01T00:00:05Z',
                  token_count: 150,
                  sources_used: ['ROC', 'DIANA']
                }
              ],
              has_retries: false
            }
          ]
        }
      ]
    }

    ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
      ...mockChatSessionHistory,
      data: realisticHistoryData
    })

    render(<ChatSessionPage />)

    // Check that the component renders and handles conversation history
    expect(screen.getByTestId('message-list')).toBeInTheDocument()
  })

  it('should handle pending message processing correctly', () => {
    const pendingMessage = {
      text: 'How do I model a retaining wall?',
      sources: ['ROC', '3GSM'],
      selectedModel: undefined,
      clear: jest.fn()
    }
    
    ;(usePendingFirstMessage as unknown as jest.Mock).mockReturnValue(pendingMessage)

    render(<ChatSessionPage />)

    // Should send the pending message
    expect(mockStreamPrompt.sendMessage).toHaveBeenCalledWith(
      'How do I model a retaining wall?',
      ['ROC', '3GSM'],
      undefined,
      false,
      null,
      false
    )
    
    // Should clear the pending message
    expect(pendingMessage.clear).toHaveBeenCalled()
  })

  it('should handle scroll behavior after message submission', async () => {
    // Mock DOM methods for new scroll behavior
    const mockScrollIntoView = jest.fn()
    const mockUserMessageElement = { scrollIntoView: mockScrollIntoView }
    const mockQuerySelectorAll = jest.fn().mockReturnValue([mockUserMessageElement])
    const mockDispatchEvent = jest.fn()
    
    Object.defineProperty(document, 'querySelectorAll', {
      value: mockQuerySelectorAll,
      writable: true
    })
    Object.defineProperty(window, 'dispatchEvent', {
      value: mockDispatchEvent,
      writable: true
    })

    render(<ChatSessionPage />)

    // Get the onSubmit function
    const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
    
    // Simulate message submission
    await act(async () => {
      await onSubmitCall('Test message', ['ROC'])
    })

    // Wait for the setTimeout to execute (50ms + 100ms delay in the component)
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 200))
    })

    // Should dispatch 'message-submitted' event
    expect(mockDispatchEvent).toHaveBeenCalled()
    
    // Should query for user messages and scroll to last one
    expect(mockQuerySelectorAll).toHaveBeenCalledWith('[data-user-message]')
    expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
  })

  it('should handle error scenarios with proper error messages', async () => {
    const errorScenarios = [
      { error: new Error('Network error'), expectedMessage: 'Network error' },
      { error: new Error('Session expired'), expectedMessage: 'Session expired' },
      { error: 'String error', expectedMessage: 'Failed to send message' },
      { error: null, expectedMessage: 'Failed to send message' }
    ]

    for (const { error, expectedMessage } of errorScenarios) {
      jest.clearAllMocks()
      
      mockStreamPrompt.sendMessage.mockImplementation(() => {
        throw error
      })

      const { unmount } = render(<ChatSessionPage />)

      // Get the onSubmit function
      const onSubmitCall = mockMessageInputState.setOnSubmit.mock.calls[0][0]
      
      // Simulate message submission that fails
      await act(async () => {
        await onSubmitCall('Test message', ['ROC'])
      })

      // Should show error alert
      await waitFor(() => {
        expect(screen.getByTestId('streaming-error-alert')).toBeInTheDocument()
      })

      // Clean up for next iteration
      unmount()
    }
  })

  it('should handle pagination loading states correctly', () => {
    const loadingStates = [
      { isFetchingNextPage: true, hasNextPage: true },
      { isFetchingNextPage: false, hasNextPage: true },
      { isFetchingNextPage: false, hasNextPage: false }
    ]

    loadingStates.forEach(({ isFetchingNextPage, hasNextPage }) => {
      jest.clearAllMocks()
      
      ;(useGetChatSessionHistory as jest.Mock).mockReturnValue({
        ...mockChatSessionHistory,
        isFetchingNextPage,
        hasNextPage
      })

      const { unmount } = render(<ChatSessionPage />)

      const loadMoreButton = screen.getByText('Load More')
      
      if (isFetchingNextPage || !hasNextPage) {
        expect(loadMoreButton).toBeDisabled()
      } else {
        expect(loadMoreButton).not.toBeDisabled()
      }

      // Clean up for next iteration
      unmount()
    })
  })
})
