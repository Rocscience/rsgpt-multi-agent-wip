import { render, screen, fireEvent } from '@testing-library/react';
import { PortalAccountAlert, SessionCreationErrorAlert, StreamingErrorAlert } from '@/components/alerts/alerts';

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Alert: ({ children, title, description, endContent, color, variant, isClosable, onClose, ...props }: any) => (
    <div 
      data-testid="alert" 
      data-color={color}
      data-variant={variant}
      data-closable={isClosable}
      {...props}
    >
      <div data-testid="alert-title">{title}</div>
      <div data-testid="alert-description">{description}</div>
      {isClosable && (
        <button data-testid="close-button" onClick={onClose}>Close</button>
      )}
      <div data-testid="alert-end-content">{endContent}</div>
      {children}
    </div>
  ),
  Button: ({ children, onClick, isLoading, as: Component = 'button', href, ...props }: any) => {
    if (Component === 'a' || href) {
      return (
        <a href={href} {...props} data-testid="button">
          {isLoading ? 'Loading...' : children}
        </a>
      );
    }
    return (
      <button onClick={onClick} {...props} data-testid="button">
        {isLoading ? 'Loading...' : children}
      </button>
    );
  },
  Link: ({ children, href, ...props }: any) => (
    <a href={href} {...props} data-testid="link">{children}</a>
  )
}));

describe('PortalAccountAlert', () => {
  it('should render with basic props', () => {
    render(<PortalAccountAlert />);
    
    expect(screen.getByTestId('alert')).toBeInTheDocument();
    expect(screen.getByTestId('alert-title')).toHaveTextContent('Your account is missing information');
    expect(screen.getByTestId('alert-description')).toHaveTextContent('Please complete your portal account information to continue.');
  });

  it('should have correct styling attributes', () => {
    render(<PortalAccountAlert />);
    
    const alert = screen.getByTestId('alert');
    expect(alert).toHaveAttribute('data-color', 'warning');
    expect(alert).toHaveAttribute('data-variant', 'faded');
  });

  it('should render portal link button', () => {
    render(<PortalAccountAlert />);
    
    const buttons = screen.getAllByTestId('button');
    const portalButton = buttons.find(btn => btn.textContent === 'Go to RocPortal');
    
    expect(portalButton).toBeInTheDocument();
    expect(portalButton).toHaveAttribute('href', 'https://www.rocscience.com/portal');
    expect(portalButton).toHaveAttribute('target', '_blank');
  });

  it('should render retry button when onRetry is provided', () => {
    const mockRetry = jest.fn();
    render(<PortalAccountAlert onRetry={mockRetry} />);
    
    const retryButton = screen.getByText('Retry');
    expect(retryButton).toBeInTheDocument();
    
    fireEvent.click(retryButton);
    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it('should not render retry button when onRetry is not provided', () => {
    render(<PortalAccountAlert />);
    
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });

  it('should show loading state on retry button', () => {
    const mockRetry = jest.fn();
    render(<PortalAccountAlert onRetry={mockRetry} isLoading={true} />);
    
    const retryButton = screen.getByText('Loading...');
    expect(retryButton).toBeInTheDocument();
  });
});

describe('SessionCreationErrorAlert', () => {
  const mockRetry = jest.fn();
  const mockDismiss = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render with required props', () => {
    render(<SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    expect(screen.getByTestId('alert')).toBeInTheDocument();
    expect(screen.getByTestId('alert-title')).toHaveTextContent('Failed to create session');
    expect(screen.getByTestId('alert-description')).toHaveTextContent("We couldn't create your chat session. Please try again.");
  });

  it('should have correct styling attributes', () => {
    render(<SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const alert = screen.getByTestId('alert');
    expect(alert).toHaveAttribute('data-color', 'danger');
    expect(alert).toHaveAttribute('data-variant', 'faded');
    expect(alert).toHaveAttribute('data-closable', 'true');
  });

  it('should call onRetry when retry button is clicked', () => {
    render(<SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);
    
    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it('should call onDismiss when close button is clicked', () => {
    render(<SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const closeButton = screen.getByTestId('close-button');
    fireEvent.click(closeButton);
    
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it('should show loading state on retry button', () => {
    render(<SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} isLoading={true} />);
    
    const retryButton = screen.getByText('Loading...');
    expect(retryButton).toBeInTheDocument();
  });
});

describe('StreamingErrorAlert', () => {
  const mockRetry = jest.fn();
  const mockDismiss = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render with required props', () => {
    render(<StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    expect(screen.getByTestId('alert')).toBeInTheDocument();
    expect(screen.getByTestId('alert-title')).toHaveTextContent('Failed to send message');
    expect(screen.getByTestId('alert-description')).toHaveTextContent("We couldn't send your message. Please try again.");
  });

  it('should have correct styling attributes', () => {
    render(<StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const alert = screen.getByTestId('alert');
    expect(alert).toHaveAttribute('data-color', 'danger');
    expect(alert).toHaveAttribute('data-variant', 'faded');
    expect(alert).toHaveAttribute('data-closable', 'true');
  });

  it('should call onRetry when retry button is clicked', () => {
    render(<StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);
    
    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it('should call onDismiss when close button is clicked', () => {
    render(<StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />);
    
    const closeButton = screen.getByTestId('close-button');
    fireEvent.click(closeButton);
    
    expect(mockDismiss).toHaveBeenCalledTimes(1);
  });

  it('should show loading state on retry button', () => {
    render(<StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} isLoading={true} />);
    
    const retryButton = screen.getByText('Loading...');
    expect(retryButton).toBeInTheDocument();
  });

  it('should have same structure as SessionCreationErrorAlert but different content', () => {
    const { container: streamingContainer } = render(
      <StreamingErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />
    );
    const { container: sessionContainer } = render(
      <SessionCreationErrorAlert onRetry={mockRetry} onDismiss={mockDismiss} />
    );
    
    // Both should have the same structure (alert with retry button and close button)
    expect(streamingContainer.querySelectorAll('[data-testid="button"]')).toHaveLength(1);
    expect(sessionContainer.querySelectorAll('[data-testid="button"]')).toHaveLength(1);
    expect(streamingContainer.querySelectorAll('[data-testid="close-button"]')).toHaveLength(1);
    expect(sessionContainer.querySelectorAll('[data-testid="close-button"]')).toHaveLength(1);
  });
});
