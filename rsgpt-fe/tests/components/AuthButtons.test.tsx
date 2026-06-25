import { render, screen } from '@testing-library/react';
import { AuthButtons } from '@/components/auth/auth-buttons';
import { User } from '@auth0/nextjs-auth0/types';

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Button: ({ children, as: Component = 'button', href, ...props }: any) => {
    if (Component === 'a' || href) {
      return <a href={href} {...props} data-testid="auth-button">{children}</a>;
    }
    return <button {...props} data-testid="auth-button">{children}</button>;
  },
  Link: ({ children, href, ...props }: any) => (
    <a href={href} {...props} data-testid="auth-link">{children}</a>
  )
}));

describe('AuthButtons', () => {
  it('should render login button when user is not provided', () => {
    render(<AuthButtons user={null} />);
    
    const loginButton = screen.getByTestId('auth-button');
    expect(loginButton).toBeInTheDocument();
    expect(loginButton).toHaveTextContent('Log in');
    expect(loginButton).toHaveAttribute('href', '/auth/login');
  });

  it('should render login button when user is undefined', () => {
    render(<AuthButtons user={undefined} />);
    
    const loginButton = screen.getByTestId('auth-button');
    expect(loginButton).toBeInTheDocument();
    expect(loginButton).toHaveTextContent('Log in');
    expect(loginButton).toHaveAttribute('href', '/auth/login');
  });

  it('should render logout link when user is provided', () => {
    const mockUser: User = {
      sub: 'auth0|123456',
      name: 'Test User',
      email: 'test@example.com'
    };

    render(<AuthButtons user={mockUser} />);
    
    const logoutLink = screen.getByTestId('auth-link');
    expect(logoutLink).toBeInTheDocument();
    expect(logoutLink).toHaveTextContent('Log out');
    expect(logoutLink).toHaveAttribute('href', '/auth/logout');
  });

  it('should render logout link for user with minimal properties', () => {
    const mockUser: User = {
      sub: 'auth0|123456'
    };

    render(<AuthButtons user={mockUser} />);
    
    const logoutLink = screen.getByTestId('auth-link');
    expect(logoutLink).toBeInTheDocument();
    expect(logoutLink).toHaveTextContent('Log out');
  });

  it('should have correct styling classes for login button', () => {
    render(<AuthButtons user={null} />);
    
    const loginButton = screen.getByTestId('auth-button');
    expect(loginButton).toHaveAttribute('color', 'primary');
  });

  it('should have correct styling classes for logout link', () => {
    const mockUser: User = {
      sub: 'auth0|123456',
      name: 'Test User'
    };

    render(<AuthButtons user={mockUser} />);
    
    const logoutLink = screen.getByTestId('auth-link');
    expect(logoutLink).toHaveAttribute('color', 'foreground');
    expect(logoutLink).toHaveAttribute('underline', 'hover');
  });
});
