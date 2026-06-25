import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SessionListItem } from '@/components/side-bar/session-list-item';
import { GetChatSessionMetaResponse } from '@/lib/types';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Create a wrapper with QueryClientProvider
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false }
  }
});

const renderWithQueryClient = (ui: React.ReactElement) => {
  const testQueryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={testQueryClient}>
      {ui}
    </QueryClientProvider>
  );
};

// Mock the navigation hook
const mockSetNavigating = jest.fn();
jest.mock('@/hooks/useNavigationState', () => ({
  useNavigationState: jest.fn(() => ({
    setNavigating: mockSetNavigating
  }))
}));

// Mock useDeleteSession
const mockDeleteSession = jest.fn();
jest.mock('@/hooks/useDeleteSession', () => ({
  useDeleteSession: jest.fn(() => ({
    mutate: mockDeleteSession,
    isPending: false
  }))
}));

// Mock Next.js navigation
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({
    push: mockPush
  }))
}));

// Mock Next.js Link
jest.mock('next/link', () => {
  return ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

// Mock DeleteSessionModal
jest.mock('@/components/side-bar/delete-session-modal', () => ({
  DeleteSessionModal: ({ isOpen, onClose, onConfirm, sessionTitle, isDeleting }: any) => (
    isOpen ? (
      <div data-testid="delete-modal">
        <span data-testid="modal-title">{sessionTitle}</span>
        <button data-testid="modal-confirm" onClick={onConfirm} disabled={isDeleting}>Confirm</button>
        <button data-testid="modal-cancel" onClick={onClose}>Cancel</button>
      </div>
    ) : null
  )
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Button: ({ children, onPress, as: Component = 'button', href, variant, isIconOnly, ...props }: any) => {
    if (Component === 'a' || href) {
      return (
        <a 
          href={href} 
          onClick={onPress} 
          data-variant={variant}
          {...props} 
          data-testid={isIconOnly ? "menu-button" : "session-button"}
        >
          {children}
        </a>
      );
    }
    return (
      <button 
        onClick={onPress} 
        data-variant={variant}
        {...props} 
        data-testid={isIconOnly ? "menu-button" : "session-button"}
      >
        {children}
      </button>
    );
  },
  Tooltip: ({ children, content, placement }: any) => (
    <div 
      data-testid="tooltip" 
      data-content={content || ''} 
      data-placement={placement}
    >
      {children}
    </div>
  ),
  Dropdown: ({ children, placement }: any) => (
    <div data-testid="dropdown" data-placement={placement}>{children}</div>
  ),
  DropdownTrigger: ({ children }: any) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
  DropdownMenu: ({ children, 'aria-label': ariaLabel }: any) => (
    <div data-testid="dropdown-menu" aria-label={ariaLabel}>{children}</div>
  ),
  DropdownItem: ({ children, onPress, className, color, startContent }: any) => (
    <button 
      data-testid="dropdown-item" 
      onClick={onPress} 
      className={className}
      data-color={color}
    >
      {startContent}
      {children}
    </button>
  )
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  EllipsisHorizontalIcon: (props: any) => <span data-testid="ellipsis-icon" {...props} />,
  TrashIcon: (props: any) => <span data-testid="trash-icon" {...props} />
}));

describe('SessionListItem', () => {
  const mockSession: GetChatSessionMetaResponse = {
    chat_session_id: 'session-123',
    title: 'Test Chat Session',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z'
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic rendering', () => {
    it('should render session title', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      expect(screen.getByText('Test Chat Session')).toBeInTheDocument();
    });

    it('should have correct href', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveAttribute('href', '/chat/session-123');
    });

    it('should have light variant when not active', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} isActive={false} />);
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveAttribute('data-variant', 'light');
    });

    it('should have solid variant when active', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} isActive={true} />);
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveAttribute('data-variant', 'solid');
    });
  });

  describe('Title display', () => {
    it('should show full title when short', () => {
      const shortSession = {
        ...mockSession,
        title: 'Short title'
      };
      
      renderWithQueryClient(<SessionListItem session={shortSession} />);
      
      expect(screen.getByText('Short title')).toBeInTheDocument();
    });

    it('should show long title with CSS truncation', () => {
      const longSession = {
        ...mockSession,
        title: 'This is a very long title that exceeds thirty-five characters'
      };
      
      renderWithQueryClient(<SessionListItem session={longSession} />);
      
      // The full title should be in the document (CSS handles truncation)
      expect(screen.getByText('This is a very long title that exceeds thirty-five characters')).toBeInTheDocument();
    });

    it('should show tooltip with full title for all sessions', () => {
      const longSession = {
        ...mockSession,
        title: 'This is a very long title that exceeds thirty-five characters'
      };
      
      renderWithQueryClient(<SessionListItem session={longSession} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', longSession.title);
    });
  });

  describe('Click behavior', () => {
    it('should call setNavigating when clicked', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      const button = screen.getByTestId('session-button');
      fireEvent.click(button);
      
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'session-123');
    });

    it('should not call closeSidebar when not mobile', () => {
      const mockCloseSidebar = jest.fn();
      renderWithQueryClient(<SessionListItem session={mockSession} closeSidebar={mockCloseSidebar} />);
      
      const button = screen.getByTestId('session-button');
      fireEvent.click(button);
      
      expect(mockCloseSidebar).not.toHaveBeenCalled();
    });

    it('should call closeSidebar when mobile', () => {
      const mockCloseSidebar = jest.fn();
      renderWithQueryClient(
        <SessionListItem 
          session={mockSession} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const button = screen.getByTestId('session-button');
      fireEvent.click(button);
      
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });

    it('should call both setNavigating and closeSidebar on mobile', () => {
      const mockCloseSidebar = jest.fn();
      renderWithQueryClient(
        <SessionListItem 
          session={mockSession} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const button = screen.getByTestId('session-button');
      fireEvent.click(button);
      
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'session-123');
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });
  });

  describe('Active state styling', () => {
    it('should have active styling when isActive is true', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} isActive={true} />);
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveClass('bg-default-300', 'shadow-sm');
    });

    it('should have inactive styling when isActive is false', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} isActive={false} />);
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveClass('bg-transparent', 'hover:bg-default-300');
    });

    it('should match current session ID for active state', () => {
      renderWithQueryClient(
        <SessionListItem 
          session={mockSession} 
          currentSessionId="session-123"
          isActive={true}
        />
      );
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveAttribute('data-variant', 'solid');
    });
  });

  describe('Tooltip behavior', () => {
    it('should have correct tooltip placement', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-placement', 'right');
    });

    it('should show title in tooltip content', () => {
      const shortSession = {
        ...mockSession,
        title: 'Short'
      };
      
      renderWithQueryClient(<SessionListItem session={shortSession} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', 'Short');
    });
  });

  describe('Delete functionality', () => {
    it('should render dropdown menu with delete option', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      expect(screen.getByTestId('dropdown')).toBeInTheDocument();
      expect(screen.getByTestId('dropdown-item')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('should show delete modal when delete is clicked', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      const deleteButton = screen.getByTestId('dropdown-item');
      fireEvent.click(deleteButton);
      
      expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
      expect(screen.getByTestId('modal-title')).toHaveTextContent('Test Chat Session');
    });

    it('should call deleteSession when confirm is clicked', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} currentSessionId="session-123" />);
      
      // Open modal
      const deleteButton = screen.getByTestId('dropdown-item');
      fireEvent.click(deleteButton);
      
      // Confirm delete
      const confirmButton = screen.getByTestId('modal-confirm');
      fireEvent.click(confirmButton);
      
      expect(mockDeleteSession).toHaveBeenCalledWith('session-123', expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function)
      }));
    });

    it('should close modal when cancel is clicked', () => {
      renderWithQueryClient(<SessionListItem session={mockSession} />);
      
      // Open modal
      const deleteButton = screen.getByTestId('dropdown-item');
      fireEvent.click(deleteButton);
      
      expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
      
      // Cancel
      const cancelButton = screen.getByTestId('modal-cancel');
      fireEvent.click(cancelButton);
      
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('should handle empty title', () => {
      const emptySession = {
        ...mockSession,
        title: ''
      };
      
      renderWithQueryClient(<SessionListItem session={emptySession} />);
      
      expect(screen.getByTestId('session-button')).toBeInTheDocument();
    });

    it('should handle special characters in title', () => {
      const specialSession = {
        ...mockSession,
        title: 'Title with @#$%^&*() characters!'
      };
      
      renderWithQueryClient(<SessionListItem session={specialSession} />);
      
      expect(screen.getByText('Title with @#$%^&*() characters!')).toBeInTheDocument();
    });

    it('should not call closeSidebar if not provided on mobile', () => {
      expect(() => {
        renderWithQueryClient(<SessionListItem session={mockSession} isMobile={true} />);
        const button = screen.getByTestId('session-button');
        fireEvent.click(button);
      }).not.toThrow();
    });
  });

  describe('Props combinations', () => {
    it('should handle all props together', () => {
      const mockCloseSidebar = jest.fn();
      renderWithQueryClient(
        <SessionListItem 
          session={mockSession}
          isActive={true}
          isMobile={true}
          closeSidebar={mockCloseSidebar}
          currentSessionId="session-123"
        />
      );
      
      const button = screen.getByTestId('session-button');
      expect(button).toHaveAttribute('data-variant', 'solid');
      
      fireEvent.click(button);
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'session-123');
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });
  });
});
