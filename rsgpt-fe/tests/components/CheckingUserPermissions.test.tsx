import { render, screen } from '@testing-library/react';
import { CheckingUserPermissions } from '@/components/ui/loading';

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Spinner: ({ color, label, ...props }: any) => (
    <div 
      data-testid="spinner" 
      data-color={color}
      aria-label={label}
      {...props}
    >
      {label}
    </div>
  )
}));

describe('CheckingUserPermissions', () => {
  it('should render spinner with correct label', () => {
    render(<CheckingUserPermissions />);
    
    const spinner = screen.getByTestId('spinner');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveTextContent('Checking your permissions...');
  });

  it('should have warning color', () => {
    render(<CheckingUserPermissions />);
    
    const spinner = screen.getByTestId('spinner');
    expect(spinner).toHaveAttribute('data-color', 'warning');
  });

  it('should have correct aria-label for accessibility', () => {
    render(<CheckingUserPermissions />);
    
    const spinner = screen.getByTestId('spinner');
    expect(spinner).toHaveAttribute('aria-label', 'Checking your permissions...');
  });

  it('should have correct container styling', () => {
    const { container } = render(<CheckingUserPermissions />);
    
    const containerDiv = container.firstChild as HTMLElement;
    expect(containerDiv).toHaveClass('flex', 'justify-center', 'py-4', 'mb-4');
  });

  it('should render without any props', () => {
    expect(() => render(<CheckingUserPermissions />)).not.toThrow();
  });
});
