import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Header } from '@/components/dashboard/header';
import { User } from '@auth0/nextjs-auth0/types';

// Mock Next.js Link
jest.mock('next/link', () => {
  return ({ children, href, className, ...props }: any) => (
    <a href={href} className={className} {...props} data-testid="next-link">
      {children}
    </a>
  );
});

// Mock RSInsightLogo
jest.mock('@/components/dashboard/rsinsight-logo', () => ({
  RSInsightLogo: ({ variant, className }: any) => (
    <div data-testid="rs-insight-logo" data-variant={variant} className={className}>
      RSInsight Logo
    </div>
  )
}));

// Mock AuthButtons
jest.mock('@/components/auth/auth-buttons', () => ({
  AuthButtons: ({ user }: any) => (
    <div data-testid="auth-buttons" data-user={user ? 'logged-in' : 'logged-out'}>
      {user ? 'Logout' : 'Login'}
    </div>
  )
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Avatar: ({ src, imgProps, className, ...props }: any) => (
    <div 
      data-testid="avatar" 
      data-src={src || ''}
      className={className}
      {...props}
    >
      <img 
        src={src} 
        onLoad={imgProps?.onLoad}
        onError={imgProps?.onError}
        data-testid="avatar-img"
      />
    </div>
  ),
  Button: ({ children, as: Component = 'button', href, prefetch, ...props }: any) => {
    if (Component === 'a' || href) {
      return <a href={href} prefetch={prefetch ? '' : undefined} {...props} data-testid="header-button">{children}</a>;
    }
    return <button {...props} data-testid="header-button">{children}</button>;
  },
  Dropdown: ({ children }: any) => <div data-testid="dropdown">{children}</div>,
  DropdownTrigger: ({ children }: any) => <div data-testid="dropdown-trigger">{children}</div>,
  DropdownMenu: ({ children, variant, className }: any) => (
    <div data-testid="dropdown-menu" data-variant={variant} className={className}>
      {children}
    </div>
  ),
  DropdownItem: ({ children, ...props }: any) => (
    <div data-testid="dropdown-item" {...props}>{children}</div>
  ),
  Skeleton: ({ className }: any) => (
    <div data-testid="skeleton" className={className}>Loading...</div>
  )
}));

describe('Header', () => {
  const mockUser: User = {
    sub: 'auth0|123456',
    name: 'John Doe',
    email: 'john.doe@example.com',
    picture: 'https://example.com/avatar.jpg'
  };

  describe('Loading state', () => {
    it('should show loading skeletons when isLoading is true', () => {
      render(<Header user={null} rocPortalAccess={null} isLoading={true} />);
      
      const skeletons = screen.getAllByTestId('skeleton');
      expect(skeletons).toHaveLength(2);
      expect(skeletons[0]).toHaveClass('h-10', 'w-16', 'rounded-lg');
      expect(skeletons[1]).toHaveClass('h-10', 'w-10', 'rounded-full');
    });

    it('should not show user content when loading', () => {
      render(<Header user={mockUser} rocPortalAccess={true} isLoading={true} />);
      
      expect(screen.queryByTestId('auth-buttons')).not.toBeInTheDocument();
      expect(screen.queryByTestId('dropdown')).not.toBeInTheDocument();
    });
  });

  describe('Logo rendering', () => {
    it('should render full logo for larger screens', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      const logos = screen.getAllByTestId('rs-insight-logo');
      const fullLogo = logos.find(logo => logo.getAttribute('data-variant') === 'full');
      expect(fullLogo).toBeInTheDocument();
      expect(fullLogo).toHaveAttribute('data-variant', 'full');
      expect(fullLogo).toHaveClass('hidden', 'sm:block', 'w-40', 'text-foreground');
    });

    it('should render mark logo for small screens', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      const logos = screen.getAllByTestId('rs-insight-logo');
      const markLogo = logos.find(logo => logo.getAttribute('data-variant') === 'mark');
      expect(markLogo).toBeInTheDocument();
      expect(markLogo).toHaveClass('block', 'sm:hidden', 'w-10', 'h-10');
    });

    it('should wrap logo in home link', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      const homeLink = screen.getByTestId('next-link');
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });

  describe('User not logged in', () => {
    it('should show auth buttons when user is not logged in', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      const authButtons = screen.getByTestId('auth-buttons');
      expect(authButtons).toBeInTheDocument();
      expect(authButtons).toHaveAttribute('data-user', 'logged-out');
    });

    it('should not show chat button when user is not logged in', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      expect(screen.queryByText('Chat')).not.toBeInTheDocument();
    });

    it('should not show user dropdown when user is not logged in', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      expect(screen.queryByTestId('dropdown')).not.toBeInTheDocument();
    });
  });

  describe('User logged in', () => {
    it('should show chat button when user has access', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const chatButton = screen.getByText('Chat');
      expect(chatButton).toBeInTheDocument();
      expect(chatButton.closest('a')).toHaveAttribute('href', '/chat');
    });

    it('should not show chat button when user has no access', () => {
      render(<Header user={mockUser} rocPortalAccess={false} />);
      
      expect(screen.queryByText('Chat')).not.toBeInTheDocument();
    });

    it('should show chat button when rocPortalAccess is null (loading)', () => {
      render(<Header user={mockUser} rocPortalAccess={null} />);
      
      const chatButton = screen.getByText('Chat');
      expect(chatButton).toBeInTheDocument();
    });

    it('should show user dropdown', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      expect(screen.getByTestId('dropdown')).toBeInTheDocument();
      expect(screen.getByTestId('dropdown-trigger')).toBeInTheDocument();
      expect(screen.getByTestId('dropdown-menu')).toBeInTheDocument();
    });

    it('should show auth buttons in dropdown', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const authButtons = screen.getByTestId('auth-buttons');
      expect(authButtons).toBeInTheDocument();
      expect(authButtons).toHaveAttribute('data-user', 'logged-in');
    });
  });

  describe('Avatar handling', () => {
    it('should show avatar with user picture', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const avatar = screen.getByTestId('avatar');
      expect(avatar).toHaveAttribute('data-src', 'https://example.com/avatar.jpg');
    });

    it('should show skeleton while avatar is loading', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      // Initially should show skeleton
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });

    it('should hide skeleton when avatar loads', async () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      // Initially, avatar should have opacity-0 class while loading
      const avatar = screen.getByTestId('avatar');
      expect(avatar).toHaveClass('opacity-0');
      
      const avatarImg = screen.getByTestId('avatar-img');
      fireEvent.load(avatarImg);
      
      // After load, skeleton should be hidden and avatar should be visible (no opacity-0 class)
      await waitFor(() => {
        const avatarAfterLoad = screen.getByTestId('avatar');
        expect(avatarAfterLoad).not.toHaveClass('opacity-0');
      });
    });

    it('should handle avatar load error', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const avatarImg = screen.getByTestId('avatar-img');
      fireEvent.error(avatarImg);
      
      // Should not throw error
      expect(screen.getByTestId('avatar')).toBeInTheDocument();
    });

    it('should reset loading state when user picture changes', () => {
      const { rerender } = render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const newUser = {
        ...mockUser,
        picture: 'https://example.com/new-avatar.jpg'
      };
      
      rerender(<Header user={newUser} rocPortalAccess={true} />);
      
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });

    it('should handle user without picture', () => {
      const userWithoutPicture = {
        ...mockUser,
        picture: undefined
      };
      
      render(<Header user={userWithoutPicture} rocPortalAccess={true} />);
      
      const avatar = screen.getByTestId('avatar');
      expect(avatar).toHaveAttribute('data-src', '');
    });
  });

  describe('Header layout and styling', () => {
    it('should have correct header structure', () => {
      const { container } = render(<Header user={null} rocPortalAccess={null} />);
      
      const header = container.querySelector('header');
      expect(header).toHaveClass(
        'max-w-full',
        'px-8',
        'py-6',
        'bg-background',
        'flex',
        'justify-between',
        'items-center',
        'relative',
        'sticky',
        'top-0',
        'z-10'
      );
    });

    it('should have logo positioned correctly', () => {
      render(<Header user={null} rocPortalAccess={null} />);
      
      const logoLink = screen.getByTestId('next-link');
      expect(logoLink).toHaveClass(
        'absolute',
        'transform',
        'sm:left-0',
        'md:left-1/2',
        'md:-translate-x-1/2'
      );
    });

    it('should have user controls positioned correctly', () => {
      const { container } = render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const userControls = container.querySelector('.flex.gap-4.items-center.ml-auto');
      expect(userControls).toBeInTheDocument();
    });
  });

  describe('Dropdown menu styling', () => {
    it('should have correct dropdown menu variant and classes', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const dropdownMenu = screen.getByTestId('dropdown-menu');
      expect(dropdownMenu).toHaveAttribute('data-variant', 'light');
      expect(dropdownMenu).toHaveClass('justify-end');
    });
  });

  describe('Button prefetch behavior', () => {
    it('should have prefetch attribute on chat button', () => {
      render(<Header user={mockUser} rocPortalAccess={true} />);
      
      const chatButton = screen.getByText('Chat').closest('a');
      expect(chatButton).toHaveAttribute('prefetch', '');
    });
  });

  describe('Props combinations', () => {
    it('should handle all states correctly', () => {
      // Test different combinations of user and rocPortalAccess
      const testCases = [
        { user: null, rocPortalAccess: null, expectedChat: false },
        { user: null, rocPortalAccess: true, expectedChat: false },
        { user: mockUser, rocPortalAccess: false, expectedChat: false },
        { user: mockUser, rocPortalAccess: true, expectedChat: true },
        { user: mockUser, rocPortalAccess: null, expectedChat: true },
      ];

      testCases.forEach(({ user, rocPortalAccess, expectedChat }) => {
        const { unmount } = render(<Header user={user} rocPortalAccess={rocPortalAccess} />);
        
        if (expectedChat) {
          expect(screen.queryByText('Chat')).toBeInTheDocument();
        } else {
          expect(screen.queryByText('Chat')).not.toBeInTheDocument();
        }
        
        unmount();
      });
    });
  });
});
