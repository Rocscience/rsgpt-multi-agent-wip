import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SidebarUserProfile } from '@/components/side-bar/user-profile';
import { User } from '@auth0/nextjs-auth0/types';

// Mock Auth0
const mockUser: User = {
  sub: 'auth0|123456',
  name: 'John Doe',
  email: 'john.doe@example.com',
  picture: 'https://example.com/avatar.jpg'
};

jest.mock('@auth0/nextjs-auth0', () => ({
  useUser: jest.fn(() => ({
    user: mockUser,
    isLoading: false
  }))
}));

// Mock hooks
const mockQuotaInfo = {
  questions_used: 5,
  question_quota: 100,
  agent_quota_used: 2,
  agent_quota: 50,
  organization_name: 'Test Organization'
};

jest.mock('@/hooks/useGetQuotaInfo', () => ({
  useGetQuotaInfo: jest.fn(() => ({
    data: mockQuotaInfo,
    isPending: false
  }))
}));

// Mock useAgentMode hook
jest.mock('@/hooks/useAgentMode', () => ({
  useAgentMode: jest.fn(() => ({
    isAgentMode: false
  }))
}));

// Mock SettingsModalContext
const mockOpenSettingsModal = jest.fn();
const mockCloseSettingsModal = jest.fn();
jest.mock('@/contexts/SettingsModalContext', () => ({
  useSettingsModal: jest.fn(() => ({
    isOpen: false,
    openSettingsModal: mockOpenSettingsModal,
    closeSettingsModal: mockCloseSettingsModal
  }))
}));

// Mock avatar utility
jest.mock('@/lib/avatar', () => ({
  getProxiedAvatarUrl: jest.fn((url) => url)
}));

// Mock AccountSettings component
jest.mock('@/components/side-bar/settings/account-settings', () => ({
  AccountSettings: ({ organizationName }: any) => (
    <div data-testid="account-settings" data-org={organizationName}>
      Account Settings Content
    </div>
  )
}));

// Mock DeviceInfo component
jest.mock('@/components/side-bar/settings/device-info', () => ({
  DeviceInfo: ({ onRefetchReady }: any) => {
    // Call onRefetchReady with a mock function if provided
    if (onRefetchReady) {
      onRefetchReady(() => Promise.resolve());
    }
    return <div data-testid="device-info">Device Info Content</div>;
  }
}));

// Mock ThemeSwitcher component
jest.mock('@/components/side-bar/settings/theme-switcher', () => ({
  ThemeSwitcher: () => <div data-testid="theme-switcher">Theme Switcher</div>
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Button: ({ children, onPress, isIconOnly, fullWidth, variant, ...props }: any) => (
    <button 
      onClick={onPress} 
      data-icon-only={isIconOnly}
      data-full-width={fullWidth}
      data-variant={variant}
      {...props} 
      data-testid="profile-button"
    >
      {children}
    </button>
  ),
  Avatar: ({ src, name, size, className, imgProps, ...props }: any) => (
    <div 
      data-testid="avatar" 
      data-src={src}
      data-name={name}
      data-size={size}
      className={className}
      {...props}
    >
      <img 
        src={src} 
        alt={name}
        onLoad={imgProps?.onLoad}
        onError={imgProps?.onError}
        data-testid="avatar-img"
      />
    </div>
  ),
  Tooltip: ({ children, content, placement }: any) => (
    <div data-testid="tooltip" data-content={content} data-placement={placement}>
      {children}
    </div>
  ),
  Spinner: ({ size, color }: any) => (
    <div data-testid="spinner" data-size={size} data-color={color}>Loading...</div>
  ),
  Skeleton: ({ className }: any) => (
    <div data-testid="skeleton" className={className}>Loading skeleton</div>
  ),
  Modal: ({ children, isOpen, onClose, size, className, placement }: any) => (
    isOpen ? (
      <div data-testid="modal" data-size={size} className={className} data-placement={placement}>
        {children}
      </div>
    ) : null
  ),
  ModalContent: ({ children }: any) => (
    <div data-testid="modal-content">{children}</div>
  ),
  ModalHeader: ({ children }: any) => (
    <div data-testid="modal-header">{children}</div>
  ),
  ModalBody: ({ children }: any) => (
    <div data-testid="modal-body">{children}</div>
  ),
  ModalFooter: ({ children }: any) => (
    <div data-testid="modal-footer">{children}</div>
  ),
  Divider: () => <div data-testid="divider" />,
  Alert: ({ children, color, variant, title }: any) => (
    <div data-testid="alert" data-color={color} data-variant={variant} data-title={title}>
      {children}
    </div>
  ),
  Link: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
  Tabs: ({ children, selectedKey, onSelectionChange }: any) => (
    <div data-testid="tabs" data-selected-key={selectedKey} onClick={() => onSelectionChange?.('account-settings')}>
      {children}
    </div>
  ),
  Tab: ({ children, key, title }: any) => (
    <div data-testid="tab" data-key={key} data-title={title}>
      {children}
    </div>
  ),
  Table: ({ children, removeWrapper, className }: any) => (
    <div data-testid="table" data-remove-wrapper={removeWrapper} className={className}>
      {children}
    </div>
  ),
  TableHeader: ({ children }: any) => (
    <div data-testid="table-header">{children}</div>
  ),
  TableBody: ({ children, emptyContent }: any) => (
    <div data-testid="table-body" data-empty-content={emptyContent}>
      {children}
    </div>
  ),
  TableRow: ({ children, key }: any) => (
    <div data-testid="table-row" data-key={key}>
      {children}
    </div>
  ),
  TableColumn: ({ children }: any) => (
    <div data-testid="table-column">{children}</div>
  ),
  TableCell: ({ children, className }: any) => (
    <div data-testid="table-cell" className={className}>
      {children}
    </div>
  ),
  Dropdown: ({ children }: any) => (
    <div data-testid="dropdown">{children}</div>
  ),
  DropdownTrigger: ({ children }: any) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
  DropdownMenu: ({ children, variant, className, onAction }: any) => (
    <div data-testid="dropdown-menu" data-variant={variant} className={className} onClick={() => onAction?.('light')}>
      {children}
    </div>
  ),
  DropdownItem: ({ children, key, startContent }: any) => (
    <div data-testid="dropdown-item" data-key={key}>
      {startContent}
      {children}
    </div>
  ),
}));

import { useUser } from '@auth0/nextjs-auth0';
import { useGetQuotaInfo } from '@/hooks/useGetQuotaInfo';
import { useSettingsModal } from '@/contexts/SettingsModalContext';

describe('SidebarUserProfile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Reset mocks to default values
    (useUser as jest.Mock).mockReturnValue({
      user: mockUser,
      isLoading: false
    });
    
    (useGetQuotaInfo as jest.Mock).mockReturnValue({
      data: mockQuotaInfo,
      isPending: false
    });
    
    (useSettingsModal as jest.Mock).mockReturnValue({
      isOpen: false,
      openSettingsModal: mockOpenSettingsModal,
      closeSettingsModal: mockCloseSettingsModal
    });
  });

  describe('Loading and user states', () => {
    it('should return null when user is loading', () => {
      (useUser as jest.Mock).mockReturnValue({
        user: null,
        isLoading: true
      });

      const { container } = render(<SidebarUserProfile />);
      expect(container.firstChild).toBeNull();
    });

    it('should return null when no user', () => {
      (useUser as jest.Mock).mockReturnValue({
        user: null,
        isLoading: false
      });

      const { container } = render(<SidebarUserProfile />);
      expect(container.firstChild).toBeNull();
    });

    it('should render when user is available', () => {
      render(<SidebarUserProfile />);
      
      expect(screen.getByTestId('profile-button')).toBeInTheDocument();
      expect(screen.getByTestId('avatar')).toBeInTheDocument();
    });
  });

  describe('User display name logic', () => {
    it('should use name when available', () => {
      render(<SidebarUserProfile />);
      
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    it('should use nickname when name is not available', () => {
      const userWithNickname = {
        ...mockUser,
        name: undefined,
        nickname: 'johndoe'
      };
      
      (useUser as jest.Mock).mockReturnValue({
        user: userWithNickname,
        isLoading: false
      });

      render(<SidebarUserProfile />);
      
      expect(screen.getByText('johndoe')).toBeInTheDocument();
    });

    it('should use email prefix when name and nickname are not available', () => {
      const userWithEmailOnly = {
        ...mockUser,
        name: undefined,
        nickname: undefined,
        email: 'test@example.com'
      };
      
      (useUser as jest.Mock).mockReturnValue({
        user: userWithEmailOnly,
        isLoading: false
      });

      render(<SidebarUserProfile />);
      
      expect(screen.getByText('test')).toBeInTheDocument();
    });

    it('should fallback to "User" when no identifiers available', () => {
      const userMinimal = {
        sub: 'auth0|123456'
      };
      
      (useUser as jest.Mock).mockReturnValue({
        user: userMinimal,
        isLoading: false
      });

      render(<SidebarUserProfile />);
      
      expect(screen.getByText('User')).toBeInTheDocument();
    });
  });

  describe('Expanded state (default)', () => {
    it('should render user info and quota', () => {
      render(<SidebarUserProfile />);
      
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('5 / 100 questions used')).toBeInTheDocument();
    });

    it('should show spinner when quota is pending', () => {
      (useGetQuotaInfo as jest.Mock).mockReturnValue({
        data: mockQuotaInfo,
        isPending: true
      });

      const userWithAccess = {
        ...mockUser,
        rocPortalAccess: true
      };
      
      (useUser as jest.Mock).mockReturnValue({
        user: userWithAccess,
        isLoading: false
      });

      render(<SidebarUserProfile />);
      
      expect(screen.getByTestId('spinner')).toBeInTheDocument();
    });

    it('should have full width button', () => {
      render(<SidebarUserProfile />);
      
      const button = screen.getByTestId('profile-button');
      expect(button).toHaveAttribute('data-full-width', 'true');
    });

    it('should show avatar with correct props', () => {
      render(<SidebarUserProfile />);
      
      const avatar = screen.getByTestId('avatar');
      expect(avatar).toHaveAttribute('data-src', 'https://example.com/avatar.jpg');
      expect(avatar).toHaveAttribute('data-name', 'John Doe');
      expect(avatar).toHaveAttribute('data-size', 'sm');
    });
  });

  describe('Collapsed state', () => {
    it('should render icon-only button when collapsed', () => {
      render(<SidebarUserProfile isCollapsed={true} />);
      
      const button = screen.getByTestId('profile-button');
      expect(button).toHaveAttribute('data-icon-only', 'true');
    });

    it('should not show user name and quota when collapsed', () => {
      render(<SidebarUserProfile isCollapsed={true} />);
      
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      expect(screen.queryByText('5 / 100 questions used')).not.toBeInTheDocument();
    });

    it('should still show avatar when collapsed', () => {
      render(<SidebarUserProfile isCollapsed={true} />);
      
      expect(screen.getByTestId('avatar')).toBeInTheDocument();
    });
  });

  describe('Avatar loading states', () => {
    it('should show skeleton while avatar is loading', () => {
      render(<SidebarUserProfile />);
      
      // Initially should show skeleton
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });

    it('should hide skeleton when avatar loads', () => {
      render(<SidebarUserProfile />);
      
      const avatarImg = screen.getByTestId('avatar-img');
      fireEvent.load(avatarImg);
      
      // After load, skeleton should be hidden (opacity-0 class)
      const avatar = screen.getByTestId('avatar');
      expect(avatar).not.toHaveClass('opacity-0');
    });

    it('should handle avatar load error', () => {
      render(<SidebarUserProfile />);
      
      const avatarImg = screen.getByTestId('avatar-img');
      fireEvent.error(avatarImg);
      
      // Should not throw error
      expect(screen.getByTestId('avatar')).toBeInTheDocument();
    });

    it('should reset loading state when user picture changes', () => {
      const { rerender } = render(<SidebarUserProfile />);
      
      const newUser = {
        ...mockUser,
        picture: 'https://example.com/new-avatar.jpg'
      };
      
      (useUser as jest.Mock).mockReturnValue({
        user: newUser,
        isLoading: false
      });
      
      rerender(<SidebarUserProfile />);
      
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });
  });

  describe('Modal behavior', () => {
    it('should open settings modal when button is clicked', () => {
      render(<SidebarUserProfile />);
      
      const button = screen.getByTestId('profile-button');
      fireEvent.click(button);
      
      expect(mockOpenSettingsModal).toHaveBeenCalledTimes(1);
      expect(mockOpenSettingsModal).toHaveBeenCalledWith('account-settings');
    });
  });

  // Note: URL hash management tests are complex to mock in jsdom environment
  // The component handles URL hash changes but we'll skip testing this functionality
  // in unit tests as it requires complex window.location mocking

  describe('Tooltip', () => {
    it('should have correct tooltip content', () => {
      render(<SidebarUserProfile />);
      
      const tooltip = screen.getByTestId('tooltip');
      expect(tooltip).toHaveAttribute('data-content', 'Open account settings');
      expect(tooltip).toHaveAttribute('data-placement', 'right');
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label when collapsed', () => {
      render(<SidebarUserProfile isCollapsed={true} />);
      
      const button = screen.getByTestId('profile-button');
      expect(button).toHaveAttribute('aria-label', 'Open account settings');
    });
  });

  describe('Plus access detection', () => {
    it('should show spinner for plus users when quota is pending', () => {
      const userWithAccess = {
        ...mockUser,
        rocPortalAccess: true
      } as User & { rocPortalAccess: boolean };
      
      (useUser as jest.Mock).mockReturnValue({
        user: userWithAccess,
        isLoading: false
      });

      (useGetQuotaInfo as jest.Mock).mockReturnValue({
        data: mockQuotaInfo,
        isPending: true
      });

      render(<SidebarUserProfile />);
      
      expect(screen.getByTestId('spinner')).toBeInTheDocument();
      expect(screen.getByTestId('spinner')).toHaveAttribute('data-color', 'primary');
    });
  });
});
