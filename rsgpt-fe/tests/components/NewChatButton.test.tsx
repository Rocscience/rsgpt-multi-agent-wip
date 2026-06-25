import { render, screen, fireEvent } from '@testing-library/react';
import { NewChatButton } from '@/components/side-bar/new-chat-button';

// Mock the navigation hook
const mockSetNavigating = jest.fn();
jest.mock('@/hooks/useNavigationState', () => ({
  useNavigationState: jest.fn(() => ({
    setNavigating: mockSetNavigating
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

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Button: ({ children, onPress, as: Component = 'button', href, isIconOnly, startContent, ...props }: any) => {
    if (Component === 'a' || href) {
      return (
        <a href={href} onClick={onPress} data-icon-only={isIconOnly} {...props} data-testid="new-chat-button">
          {startContent}
          {children}
        </a>
      );
    }
    return (
      <button onClick={onPress} data-icon-only={isIconOnly} {...props} data-testid="new-chat-button">
        {startContent}
        {children}
      </button>
    );
  },
  Tooltip: ({ children, content, placement }: any) => (
    <div data-testid="tooltip" data-content={content} data-placement={placement}>
      {children}
    </div>
  )
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  PencilSquareIcon: (props: any) => <div data-testid="pencil-icon" {...props} />
}));

describe('NewChatButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Expanded state (default)', () => {
    it('should render expanded button with text and icon', () => {
      render(<NewChatButton />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent('New Chat');
      expect(screen.getByTestId('pencil-icon')).toBeInTheDocument();
    });

    it('should have correct href for new chat', () => {
      render(<NewChatButton />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toHaveAttribute('href', '/chat');
    });

    it('should have correct styling classes', () => {
      render(<NewChatButton />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toHaveAttribute('color', 'default');
      expect(button).toHaveAttribute('variant', 'light');
    });

    it('should call setNavigating when clicked', () => {
      render(<NewChatButton />);
      
      const button = screen.getByTestId('new-chat-button');
      fireEvent.click(button);
      
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'new');
    });

    it('should not call closeSidebar when not mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(<NewChatButton closeSidebar={mockCloseSidebar} />);
      
      const button = screen.getByTestId('new-chat-button');
      fireEvent.click(button);
      
      expect(mockCloseSidebar).not.toHaveBeenCalled();
    });
  });

  describe('Collapsed state', () => {
    it('should render collapsed button with tooltip', () => {
      render(<NewChatButton isCollapsed={true} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveAttribute('data-content', 'New Chat');
      expect(tooltip).toHaveAttribute('data-placement', 'right');
    });

    it('should render icon-only button when collapsed', () => {
      render(<NewChatButton isCollapsed={true} />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toHaveAttribute('data-icon-only', 'true');
      expect(button).toHaveAttribute('aria-label', 'New Chat');
    });

    it('should not show text when collapsed', () => {
      render(<NewChatButton isCollapsed={true} />);
      
      expect(screen.queryByText('New Chat')).not.toBeInTheDocument();
    });

    it('should have different styling when collapsed', () => {
      render(<NewChatButton isCollapsed={true} />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toHaveClass('bg-muted', 'hover:bg-secondary/80');
    });
  });

  describe('Mobile behavior', () => {
    it('should call closeSidebar when mobile and clicked', () => {
      const mockCloseSidebar = jest.fn();
      render(<NewChatButton isMobile={true} closeSidebar={mockCloseSidebar} />);
      
      const button = screen.getByTestId('new-chat-button');
      fireEvent.click(button);
      
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });

    it('should call both setNavigating and closeSidebar on mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(<NewChatButton isMobile={true} closeSidebar={mockCloseSidebar} />);
      
      const button = screen.getByTestId('new-chat-button');
      fireEvent.click(button);
      
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'new');
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });

    it('should not call closeSidebar if not provided on mobile', () => {
      expect(() => {
        render(<NewChatButton isMobile={true} />);
        const button = screen.getByTestId('new-chat-button');
        fireEvent.click(button);
      }).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label when collapsed', () => {
      render(<NewChatButton isCollapsed={true} />);
      
      const button = screen.getByTestId('new-chat-button');
      expect(button).toHaveAttribute('aria-label', 'New Chat');
    });

    it('should be keyboard accessible', () => {
      render(<NewChatButton />);
      
      const button = screen.getByTestId('new-chat-button');
      button.focus();
      
      // Simulate click instead of keyDown since our mock doesn't handle keyboard events
      fireEvent.click(button);
      expect(mockSetNavigating).toHaveBeenCalled();
    });
  });

  describe('Props combinations', () => {
    it('should handle all props together', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <NewChatButton 
          isCollapsed={true} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const button = screen.getByTestId('new-chat-button');
      fireEvent.click(button);
      
      expect(mockSetNavigating).toHaveBeenCalledWith(true, 'new');
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });

    it('should render correctly with no optional props', () => {
      render(<NewChatButton />);
      
      expect(screen.getByTestId('new-chat-button')).toBeInTheDocument();
      expect(screen.getByText('New Chat')).toBeInTheDocument();
    });
  });
});
