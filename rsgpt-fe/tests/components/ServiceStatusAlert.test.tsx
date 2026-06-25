import { render, screen, waitFor, act } from '@testing-library/react';
import { ServiceStatusAlert } from '@/components/alerts/service-status-banner';

// Mock the API
jest.mock('@/lib/api', () => ({
  checkServiceHealth: jest.fn()
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Alert: ({ title, description, color, variant, isClosable, onClose, ...props }: any) => (
    <div 
      data-testid="service-alert" 
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
    </div>
  )
}));

import { checkServiceHealth } from '@/lib/api';

describe('ServiceStatusAlert', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Mock window.addEventListener and removeEventListener
    global.addEventListener = jest.fn();
    global.removeEventListener = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('should not render alert initially', () => {
    render(<ServiceStatusAlert />);
    
    expect(screen.queryByTestId('service-alert')).not.toBeInTheDocument();
  });

  it('should call checkServiceHealth on mount', () => {
    render(<ServiceStatusAlert />);
    
    expect(checkServiceHealth).toHaveBeenCalledTimes(1);
  });

  it('should set up periodic health checks', () => {
    render(<ServiceStatusAlert />);
    
    // Fast-forward 30 seconds
    act(() => {
      jest.advanceTimersByTime(30000);
    });
    
    expect(checkServiceHealth).toHaveBeenCalledTimes(2);
    
    // Fast-forward another 30 seconds
    act(() => {
      jest.advanceTimersByTime(30000);
    });
    
    expect(checkServiceHealth).toHaveBeenCalledTimes(3);
  });

  it('should set up event listeners for service events', () => {
    render(<ServiceStatusAlert />);
    
    expect(global.addEventListener).toHaveBeenCalledWith('service-unavailable', expect.any(Function));
    expect(global.addEventListener).toHaveBeenCalledWith('service-recovered', expect.any(Function));
  });

  it('should show danger alert when service becomes unavailable', async () => {
    render(<ServiceStatusAlert />);
    
    // Simulate service unavailable event
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
    });
    
    await waitFor(() => {
      expect(screen.getByTestId('service-alert')).toBeInTheDocument();
    });
    
    expect(screen.getByTestId('alert-title')).toHaveTextContent('Service Unavailable');
    expect(screen.getByTestId('alert-description')).toHaveTextContent("Some features may not work. We're working to restore service.");
    
    const alert = screen.getByTestId('service-alert');
    expect(alert).toHaveAttribute('data-color', 'danger');
    expect(alert).toHaveAttribute('data-closable', 'false');
  });

  it('should show success alert when service recovers', async () => {
    render(<ServiceStatusAlert />);
    
    // First trigger service unavailable
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
    });
    
    // Then trigger service recovered
    const serviceRecoveredHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-recovered')?.[1];
    
    act(() => {
      serviceRecoveredHandler();
    });
    
    await waitFor(() => {
      expect(screen.getByTestId('alert-title')).toHaveTextContent('Service Recovered');
    });
    
    expect(screen.getByTestId('alert-description')).toHaveTextContent('All features are now available.');
    
    const alert = screen.getByTestId('service-alert');
    expect(alert).toHaveAttribute('data-color', 'success');
    expect(alert).toHaveAttribute('data-closable', 'true');
  });

  it('should auto-hide success alert after 3 seconds', async () => {
    render(<ServiceStatusAlert />);
    
    // Trigger service unavailable then recovered
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    const serviceRecoveredHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-recovered')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
    });
    
    act(() => {
      serviceRecoveredHandler();
    });
    
    // Alert should be visible
    await waitFor(() => {
      expect(screen.getByTestId('service-alert')).toBeInTheDocument();
    });
    
    // Fast-forward 3 seconds
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    
    await waitFor(() => {
      expect(screen.queryByTestId('service-alert')).not.toBeInTheDocument();
    });
  });

  it('should have correct container styling', () => {
    render(<ServiceStatusAlert />);
    
    // Trigger service unavailable to show the alert
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
    });
    
    const container = screen.getByTestId('service-alert').parentElement;
    expect(container).toHaveClass('fixed', 'top-4', 'right-4', 'z-50', 'max-w-md');
  });

  it('should clean up intervals and event listeners on unmount', () => {
    const { unmount } = render(<ServiceStatusAlert />);
    
    unmount();
    
    expect(global.removeEventListener).toHaveBeenCalledWith('service-unavailable', expect.any(Function));
    expect(global.removeEventListener).toHaveBeenCalledWith('service-recovered', expect.any(Function));
  });

  it('should handle manual close for success alert', async () => {
    render(<ServiceStatusAlert />);
    
    // Trigger service recovery to show closable alert
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    const serviceRecoveredHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-recovered')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
      serviceRecoveredHandler();
    });
    
    await waitFor(() => {
      expect(screen.getByTestId('close-button')).toBeInTheDocument();
    });
    
    // Click close button
    act(() => {
      screen.getByTestId('close-button').click();
    });
    
    await waitFor(() => {
      expect(screen.queryByTestId('service-alert')).not.toBeInTheDocument();
    });
  });

  it('should not show close button for danger alert', async () => {
    render(<ServiceStatusAlert />);
    
    // Trigger service unavailable
    const serviceUnavailableHandler = (global.addEventListener as jest.Mock).mock.calls
      .find(call => call[0] === 'service-unavailable')?.[1];
    
    act(() => {
      serviceUnavailableHandler();
    });
    
    await waitFor(() => {
      expect(screen.getByTestId('service-alert')).toBeInTheDocument();
    });
    
    expect(screen.queryByTestId('close-button')).not.toBeInTheDocument();
  });
});
