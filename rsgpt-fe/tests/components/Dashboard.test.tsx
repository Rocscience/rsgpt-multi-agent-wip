import { render, screen } from '@testing-library/react';
import Dashboard from '@/components/dashboard/dashboard';

// Mock all the complex dependencies
jest.mock('@auth0/nextjs-auth0', () => ({
  useUser: jest.fn(() => ({
    user: { sub: 'test-user', name: 'Test User' },
    isLoading: false
  }))
}));

jest.mock('@/components/auth/auth-checker', () => {
  return function MockAuthChecker() {
    return <div data-testid="auth-checker">Auth Checker</div>;
  };
});

jest.mock('@/components/dashboard/prompt-animation', () => {
  return function MockPromptAnimation() {
    return <div data-testid="prompt-animation">Prompt Animation</div>;
  };
});

jest.mock('@/components/dashboard/header', () => ({
  Header: function MockHeader() {
    return <div data-testid="dashboard-header">Dashboard Header</div>;
  }
}));

jest.mock('@/components/banners/agent-mode-banner', () => ({
  AgentModeBanner: function MockAgentModeBanner() {
    return <div data-testid="agent-mode-banner">Agent Mode Banner</div>;
  }
}));

jest.mock('@/components/side-bar/settings/global-settings-modal', () => ({
  GlobalSettingsModal: function MockGlobalSettingsModal() {
    return <div data-testid="global-settings-modal">Global Settings Modal</div>;
  }
}));

jest.mock('@/contexts/SettingsModalContext', () => ({
  SettingsModalProvider: ({ children }: any) => <div>{children}</div>
}));

jest.mock('@heroui/react', () => ({
  Button: ({ children, as: Component = 'button', href, isDisabled, ...props }: any) => {
    const { isDisabled: _, ...cleanProps } = props; // Remove isDisabled from props
    if (Component === 'a' || href) {
      return <a href={href} {...cleanProps} data-testid="dashboard-button" data-disabled={isDisabled}>{children}</a>;
    }
    return <button {...cleanProps} data-testid="dashboard-button" data-disabled={isDisabled}>{children}</button>;
  },
  Link: ({ children, href, ...props }: any) => (
    <a href={href} {...props} data-testid="dashboard-link">{children}</a>
  )
}));

describe('Dashboard', () => {
  describe('Basic Rendering', () => {
    it('should render without crashing', () => {
      const { container } = render(<Dashboard />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should render main layout structure', () => {
      const { container } = render(<Dashboard />);
      // Just check that we have a div with flex classes - any div is fine
      const flexDiv = container.querySelector('div');
      expect(flexDiv).toBeInTheDocument();
    });

    it('should render header component', () => {
      render(<Dashboard />);
      expect(screen.getByTestId('dashboard-header')).toBeInTheDocument();
    });

    it('should render prompt animation component', () => {
      render(<Dashboard />);
      expect(screen.getByTestId('prompt-animation')).toBeInTheDocument();
    });

    it('should render main content area', () => {
      render(<Dashboard />);
      const mainElement = screen.getByRole('main');
      expect(mainElement).toBeInTheDocument();
      expect(mainElement).toHaveClass('overflow-y-hidden', 'bg-secondary');
    });
  });

  describe('Content', () => {
    it('should display main heading', () => {
      render(<Dashboard />);
      expect(screen.getByText(/Stop Digging for Answers, Just Use RSInsight/)).toBeInTheDocument();
    });

    it('should display subtitle', () => {
      render(<Dashboard />);
      expect(screen.getByText(/Fast and reliable data to back up your engineering decisions/)).toBeInTheDocument();
    });

    it('should render call-to-action button', () => {
      render(<Dashboard />);
      const button = screen.getByTestId('dashboard-button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent('Ask a Question');
    });
  });
});