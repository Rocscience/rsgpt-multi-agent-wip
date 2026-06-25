import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SessionList } from '@/components/side-bar/session-list';
import { GetChatSessionMetaResponse } from '@/lib/types';

// Mock Next.js useParams
jest.mock('next/navigation', () => ({
  useParams: jest.fn(() => ({ sessionId: 'current-session-123' }))
}));

// Mock the sessions hook
const mockSessions: GetChatSessionMetaResponse[] = [
  {
    chat_session_id: 'session-1',
    title: 'First Chat Session',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  },
  {
    chat_session_id: 'session-2',
    title: 'Second Chat Session',
    created_at: '2023-01-02T00:00:00Z',
    updated_at: '2023-01-02T00:00:00Z'
  }
];

const mockInfiniteSessions = {
  data: {
    pages: [{ sessions: mockSessions }]
  },
  isLoading: false,
  error: null,
  fetchNextPage: jest.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  refetch: jest.fn()
};

jest.mock('@/hooks/useSessions', () => ({
  useInfiniteSessions: jest.fn(() => mockInfiniteSessions)
}));

// Mock SessionListItem
jest.mock('@/components/side-bar/session-list-item', () => ({
  SessionListItem: ({ session, isActive, isMobile, closeSidebar, currentSessionId }: any) => (
    <div 
      data-testid="session-list-item"
      data-session-id={session.chat_session_id}
      data-active={isActive}
      data-mobile={isMobile}
      data-current-session={currentSessionId || ''}
    >
      {session.title}
      {closeSidebar && <button onClick={closeSidebar} data-testid="close-sidebar">Close</button>}
    </div>
  )
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Skeleton: ({ className }: any) => (
    <div data-testid="skeleton" className={className}>Loading...</div>
  ),
  Alert: ({ color, variant, title, description }: any) => (
    <div 
      data-testid="alert" 
      data-color={color}
      data-variant={variant}
    >
      <div data-testid="alert-title">{title}</div>
      <div data-testid="alert-description">{description}</div>
    </div>
  ),
  Button: ({ children, onClick, isLoading, color, variant, size }: any) => (
    <button 
      onClick={onClick}
      data-loading={isLoading}
      data-color={color}
      data-variant={variant}
      data-size={size}
      data-testid="retry-button"
    >
      {children}
    </button>
  )
}));

import { useInfiniteSessions } from '@/hooks/useSessions';
import { useParams } from 'next/navigation';

// Mock IntersectionObserver
const mockIntersectionObserver = jest.fn();
mockIntersectionObserver.mockReturnValue({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
});
window.IntersectionObserver = mockIntersectionObserver;

describe('SessionList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Reset to default mock values
    (useInfiniteSessions as jest.Mock).mockReturnValue(mockInfiniteSessions);
    (useParams as jest.Mock).mockReturnValue({ sessionId: 'current-session-123' });
  });

  describe('Loading states', () => {
    it('should show skeleton loading when initially loading', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        isLoading: true,
        data: null
      });

      render(<SessionList />);
      
      const skeletons = screen.getAllByTestId('skeleton');
      expect(skeletons).toHaveLength(3);
    });

    it('should show different skeleton widths for variety', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        isLoading: true,
        data: null
      });

      render(<SessionList />);
      
      const skeletons = screen.getAllByTestId('skeleton');
      expect(skeletons[0]).toHaveClass('w-4/5');
      expect(skeletons[1]).toHaveClass('w-3/5');
      expect(skeletons[2]).toHaveClass('w-2/3');
    });

    it('should show loading skeleton when fetching next page', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        isFetchingNextPage: true
      });

      render(<SessionList />);
      
      // Should show sessions and additional loading skeleton
      expect(screen.getAllByTestId('session-list-item')).toHaveLength(2);
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });
  });

  describe('Empty state', () => {
    it('should show empty message when no sessions', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        data: { pages: [{ sessions: [] }] }
      });

      render(<SessionList />);
      
      expect(screen.getByText('No chats to show yet...')).toBeInTheDocument();
    });

    it('should not show sessions when empty', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        data: { pages: [{ sessions: [] }] }
      });

      render(<SessionList />);
      
      expect(screen.queryByTestId('session-list-item')).not.toBeInTheDocument();
    });
  });

  describe('Session rendering', () => {
    it('should render all sessions', () => {
      render(<SessionList />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems).toHaveLength(2);
      
      expect(screen.getByText('First Chat Session')).toBeInTheDocument();
      expect(screen.getByText('Second Chat Session')).toBeInTheDocument();
    });

    it('should pass correct props to SessionListItem', () => {
      render(<SessionList isMobile={true} />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems[0]).toHaveAttribute('data-session-id', 'session-1');
      expect(sessionItems[0]).toHaveAttribute('data-mobile', 'true');
      expect(sessionItems[0]).toHaveAttribute('data-current-session', 'current-session-123');
    });

    it('should determine active session correctly', () => {
      (useParams as jest.Mock).mockReturnValue({ sessionId: 'session-1' });
      
      render(<SessionList />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems[0]).toHaveAttribute('data-active', 'true');
      expect(sessionItems[1]).toHaveAttribute('data-active', 'false');
    });

    it('should pass closeSidebar function to items', () => {
      const mockCloseSidebar = jest.fn();
      render(<SessionList closeSidebar={mockCloseSidebar} />);
      
      const closeButton = screen.getAllByTestId('close-sidebar')[0];
      fireEvent.click(closeButton);
      
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });
  });

  describe('Error handling', () => {
    it('should show empty state even when there is an error and no sessions', () => {
      // The component shows empty state instead of error when no sessions are loaded
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        data: { pages: [{ sessions: [] }] }, // Empty sessions array
        error: new Error('Network error'),
        isLoading: false
      });

      render(<SessionList />);
      
      // Should show empty state, not error
      expect(screen.getByText('No chats to show yet...')).toBeInTheDocument();
      expect(screen.queryByTestId('alert')).not.toBeInTheDocument();
    });

    it('should show partial error when some sessions loaded', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        error: new Error('Network error'),
        hasNextPage: true
      });

      render(<SessionList />);
      
      expect(screen.getByTestId('alert-title')).toHaveTextContent('Failed to load more sessions');
      expect(screen.getByTestId('alert-description')).toHaveTextContent('There may be more sessions available.');
      
      const alert = screen.getByTestId('alert');
      expect(alert).toHaveAttribute('data-color', 'warning');
    });

    it('should show retry loading more button for partial error with hasNextPage', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        error: new Error('Network error'),
        hasNextPage: true
      });

      render(<SessionList />);
      
      const retryButton = screen.getByTestId('retry-button');
      expect(retryButton).toHaveTextContent('Retry Loading More');
      expect(retryButton).toHaveAttribute('data-color', 'warning');
    });

    it('should show refresh button for partial error without hasNextPage', () => {
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        error: new Error('Network error'),
        hasNextPage: false
      });

      render(<SessionList />);
      
      const retryButton = screen.getByTestId('retry-button');
      expect(retryButton).toHaveTextContent('Refresh');
    });

    it('should call fetchNextPage when retry loading more is clicked', () => {
      const mockFetchNextPage = jest.fn();
      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        error: new Error('Network error'),
        hasNextPage: true,
        fetchNextPage: mockFetchNextPage
      });

      render(<SessionList />);
      
      const retryButton = screen.getByTestId('retry-button');
      fireEvent.click(retryButton);
      
      expect(mockFetchNextPage).toHaveBeenCalledTimes(1);
    });
  });

  describe('Infinite scrolling', () => {
    it('should set up IntersectionObserver', () => {
      render(<SessionList />);
      
      expect(mockIntersectionObserver).toHaveBeenCalled();
    });

    it('should observe load more element', () => {
      const mockObserve = jest.fn();
      mockIntersectionObserver.mockReturnValue({
        observe: mockObserve,
        unobserve: jest.fn(),
        disconnect: jest.fn(),
      });

      render(<SessionList />);
      
      expect(mockObserve).toHaveBeenCalled();
    });

    it('should cleanup observer on unmount', () => {
      const mockUnobserve = jest.fn();
      mockIntersectionObserver.mockReturnValue({
        observe: jest.fn(),
        unobserve: mockUnobserve,
        disconnect: jest.fn(),
      });

      const { unmount } = render(<SessionList />);
      unmount();
      
      expect(mockUnobserve).toHaveBeenCalled();
    });
  });

  describe('Multiple pages handling', () => {
    it('should flatten sessions from multiple pages', () => {
      const multiPageData = {
        pages: [
          { sessions: [mockSessions[0]] },
          { sessions: [mockSessions[1]] }
        ]
      };

      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        data: multiPageData
      });

      render(<SessionList />);
      
      expect(screen.getAllByTestId('session-list-item')).toHaveLength(2);
    });

    it('should handle empty pages', () => {
      const emptyPageData = {
        pages: [
          { sessions: [] },
          { sessions: mockSessions }
        ]
      };

      (useInfiniteSessions as jest.Mock).mockReturnValue({
        ...mockInfiniteSessions,
        data: emptyPageData
      });

      render(<SessionList />);
      
      expect(screen.getAllByTestId('session-list-item')).toHaveLength(2);
    });
  });

  describe('Props handling', () => {
    it('should handle default props', () => {
      render(<SessionList />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems[0]).toHaveAttribute('data-mobile', 'false');
    });

    it('should pass mobile prop correctly', () => {
      render(<SessionList isMobile={true} />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems[0]).toHaveAttribute('data-mobile', 'true');
    });

    it('should handle missing sessionId in params', () => {
      (useParams as jest.Mock).mockReturnValue({});
      
      render(<SessionList />);
      
      const sessionItems = screen.getAllByTestId('session-list-item');
      expect(sessionItems[0]).toHaveAttribute('data-current-session', '');
    });
  });
});
