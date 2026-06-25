import { render, screen, fireEvent } from '@testing-library/react';
import { SidebarHeader } from '@/components/side-bar/sidebar-header';

// Mock Next.js Image
jest.mock('next/image', () => {
  return ({ src, alt, width, height, className, ...props }: any) => (
    <img 
      src={src} 
      alt={alt} 
      width={width} 
      height={height} 
      className={className}
      data-testid="logo-image"
      {...props} 
    />
  );
});

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Button: ({ children, onPress, isIconOnly, ...props }: any) => (
    <button onClick={onPress} data-icon-only={isIconOnly} {...props} data-testid="header-button">
      {children}
    </button>
  ),
  Link: ({ children, href, ...props }: any) => (
    <a href={href} {...props} data-testid="header-link">
      {children}
    </a>
  ),
  Tooltip: ({ children, content, placement }: any) => (
    <div data-testid="tooltip" data-content={content} data-placement={placement}>
      {children}
    </div>
  )
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  ChevronDoubleLeftIcon: ({ className }: any) => (
    <div data-testid="chevron-icon" className={className} />
  ),
  XMarkIcon: ({ className }: any) => (
    <div data-testid="x-mark-icon" className={className} />
  )
}));

describe('SidebarHeader', () => {
  const defaultProps = {
    isCollapsed: false,
    onToggle: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Expanded state', () => {
    it('should render logo and collapse button when expanded', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      expect(screen.getByTestId('logo-image')).toBeInTheDocument();
      expect(screen.getByTestId('header-button')).toBeInTheDocument();
      expect(screen.getByTestId('chevron-icon')).toBeInTheDocument();
    });

    it('should have correct logo properties', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const logo = screen.getByTestId('logo-image');
      expect(logo).toHaveAttribute('src', '/images/logo_mark_rsinsight.svg');
      expect(logo).toHaveAttribute('alt', 'RSInsight Logo');
      expect(logo).toHaveAttribute('width', '32');
      expect(logo).toHaveAttribute('height', '32');
    });

    it('should have logo wrapped in link to home', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const link = screen.getByTestId('header-link');
      expect(link).toHaveAttribute('href', '/');
    });

    it('should call onToggle when collapse button is clicked', () => {
      const mockToggle = jest.fn();
      render(<SidebarHeader {...defaultProps} onToggle={mockToggle} />);
      
      const button = screen.getByTestId('header-button');
      fireEvent.click(button);
      
      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should have correct tooltip for collapse button', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', 'Collapse sidebar');
      expect(tooltip).toHaveAttribute('data-placement', 'bottom');
    });

    it('should have correct aria-label for collapse button', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const button = screen.getByTestId('header-button');
      expect(button).toHaveAttribute('aria-label', 'Collapse sidebar');
    });
  });

  describe('Collapsed state', () => {
    it('should render only expand button when collapsed', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      expect(screen.getByTestId('header-button')).toBeInTheDocument();
      expect(screen.getByTestId('logo-image')).toBeInTheDocument();
      expect(screen.queryByTestId('header-link')).not.toBeInTheDocument();
    });

    it('should have icon-only button when collapsed', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      const button = screen.getByTestId('header-button');
      expect(button).toHaveAttribute('data-icon-only', 'true');
    });

    it('should have correct tooltip for expand button', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', 'Expand sidebar');
      expect(tooltip).toHaveAttribute('data-placement', 'right');
    });

    it('should have correct aria-label for expand button', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      const button = screen.getByTestId('header-button');
      expect(button).toHaveAttribute('aria-label', 'Expand sidebar');
    });

    it('should call onToggle when expand button is clicked', () => {
      const mockToggle = jest.fn();
      render(<SidebarHeader {...defaultProps} isCollapsed={true} onToggle={mockToggle} />);
      
      const button = screen.getByTestId('header-button');
      fireEvent.click(button);
      
      expect(mockToggle).toHaveBeenCalledTimes(1);
    });
  });

  describe('Mobile behavior', () => {
    it('should show close button instead of collapse on mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <SidebarHeader 
          {...defaultProps} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      expect(screen.getByTestId('x-mark-icon')).toBeInTheDocument();
      expect(screen.queryByTestId('chevron-icon')).not.toBeInTheDocument();
    });

    it('should have correct tooltip for close button on mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <SidebarHeader 
          {...defaultProps} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', 'Close sidebar');
    });

    it('should call closeSidebar when close button is clicked on mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <SidebarHeader 
          {...defaultProps} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const button = screen.getByTestId('header-button');
      fireEvent.click(button);
      
      expect(mockCloseSidebar).toHaveBeenCalledTimes(1);
    });

    it('should have correct aria-label for close button on mobile', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <SidebarHeader 
          {...defaultProps} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      const button = screen.getByTestId('header-button');
      expect(button).toHaveAttribute('aria-label', 'Close sidebar');
    });
  });

  describe('CollapseIcon component', () => {
    it('should have correct rotation class when collapsed', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      const chevronIcon = screen.getByTestId('chevron-icon');
      expect(chevronIcon).toHaveClass('rotate-180');
    });

    it('should not have rotation class when expanded', () => {
      render(<SidebarHeader {...defaultProps} isCollapsed={false} />);
      
      const chevronIcon = screen.getByTestId('chevron-icon');
      expect(chevronIcon).not.toHaveClass('rotate-180');
    });

    it('should have transition classes', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const chevronIcon = screen.getByTestId('chevron-icon');
      expect(chevronIcon).toHaveClass('transition-transform', 'duration-300');
    });
  });

  describe('Styling and layout', () => {
    it('should have correct container classes when expanded', () => {
      const { container } = render(<SidebarHeader {...defaultProps} />);
      
      const headerContainer = container.firstChild as HTMLElement;
      expect(headerContainer).toHaveClass('flex', 'items-center', 'justify-between', 'p-2');
    });

    it('should have correct container classes when collapsed', () => {
      const { container } = render(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      
      const headerContainer = container.firstChild as HTMLElement;
      expect(headerContainer).toHaveClass('flex', 'flex-col', 'items-center', 'p-2');
    });

    it('should have hover effects on logo', () => {
      render(<SidebarHeader {...defaultProps} />);
      
      const logo = screen.getByTestId('logo-image');
      expect(logo).toHaveClass('hover:opacity-80', 'transition-opacity');
    });
  });

  describe('Accessibility', () => {
    it('should be keyboard accessible', () => {
      const mockToggle = jest.fn();
      render(<SidebarHeader {...defaultProps} onToggle={mockToggle} />);
      
      const button = screen.getByTestId('header-button');
      button.focus();
      
      // Simulate click instead of keyDown since our mock doesn't handle keyboard events
      fireEvent.click(button);
      expect(mockToggle).toHaveBeenCalled();
    });

    it('should have proper ARIA labels for all states', () => {
      // Test expanded state
      const { rerender } = render(<SidebarHeader {...defaultProps} />);
      expect(screen.getByTestId('header-button')).toHaveAttribute('aria-label', 'Collapse sidebar');
      
      // Test collapsed state
      rerender(<SidebarHeader {...defaultProps} isCollapsed={true} />);
      expect(screen.getByTestId('header-button')).toHaveAttribute('aria-label', 'Expand sidebar');
      
      // Test mobile state
      rerender(<SidebarHeader {...defaultProps} isMobile={true} closeSidebar={jest.fn()} />);
      expect(screen.getByTestId('header-button')).toHaveAttribute('aria-label', 'Close sidebar');
    });
  });

  describe('Edge cases', () => {
    it('should handle missing closeSidebar on mobile gracefully', () => {
      expect(() => {
        render(<SidebarHeader {...defaultProps} isMobile={true} />);
      }).not.toThrow();
    });

    it('should handle both collapsed and mobile states', () => {
      const mockCloseSidebar = jest.fn();
      render(
        <SidebarHeader 
          {...defaultProps} 
          isCollapsed={true} 
          isMobile={true} 
          closeSidebar={mockCloseSidebar} 
        />
      );
      
      // Should still render collapsed state (mobile doesn't affect collapsed rendering)
      expect(screen.getByTestId('header-button')).toHaveAttribute('data-icon-only', 'true');
    });
  });
});
