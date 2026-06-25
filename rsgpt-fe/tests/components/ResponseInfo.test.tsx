import { render, screen } from '@testing-library/react';
import { ResponseInfo } from '@/components/chat/display/response-info';

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Popover: ({ children }: any) => <div data-testid="popover">{children}</div>,
  PopoverTrigger: ({ children }: any) => <div data-testid="popover-trigger">{children}</div>,
  PopoverContent: ({ children }: any) => <div data-testid="popover-content">{children}</div>,
  Button: ({ children, isIconOnly, variant, size, onPress, ...props }: any) => (
    <button 
      {...props} 
      onClick={onPress}
      data-icon-only={isIconOnly}
      data-variant={variant}
      data-size={size}
      data-testid="button"
    >
      {children}
    </button>
  )
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  EllipsisHorizontalIcon: (props: any) => <div data-testid="ellipsis-icon" {...props} />
}));

describe('ResponseInfo', () => {
  it('should not render when no data is provided', () => {
    const { container } = render(<ResponseInfo />);
    expect(container.firstChild).toBeNull();
  });

  it('should not render when all props are empty/undefined', () => {
    const { container } = render(
      <ResponseInfo
        sourcesUsed={[]}
        responseTimeMs={undefined}
        tokenCount={undefined}
        displayName={undefined}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('should render when sources are provided', () => {
    render(<ResponseInfo sourcesUsed={['ROC', 'DIANA']} />);

    expect(screen.getByTestId('popover')).toBeInTheDocument();
    expect(screen.getByTestId('button')).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('ROC, DIANA')).toBeInTheDocument();
  });

  it('should render when response metadata is provided', () => {
    render(<ResponseInfo responseTimeMs={1500} tokenCount={250} />);
    
    expect(screen.getByTestId('popover')).toBeInTheDocument();
    expect(screen.getByText('Performance')).toBeInTheDocument();
    // Updated: format is now "{seconds} sec" instead of "{ms}ms"
    expect(screen.getByText('Response time: 1.50 sec')).toBeInTheDocument();
    expect(screen.getByText('Tokens: 250')).toBeInTheDocument();
  });

  it('should render model name when sources are provided', () => {
    render(<ResponseInfo sourcesUsed={['ROC']} displayName="gpt-4o" />);

    expect(screen.getByText('Model')).toBeInTheDocument();
    expect(screen.getByText('gpt-4o')).toBeInTheDocument();
  });

  it('should render both sources and metadata sections', () => {
    render(
      <ResponseInfo
        sourcesUsed={['ROC', '3GSM']}
        responseTimeMs={2000}
        tokenCount={300}
        displayName="gpt-4.1-2025-04-14"
      />
    );

    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('ROC, 3GSM')).toBeInTheDocument();
    expect(screen.getByText('gpt-4.1-2025-04-14')).toBeInTheDocument();
    expect(screen.getByText('Performance')).toBeInTheDocument();
    // Updated: format is now "{seconds} sec" instead of "{ms}ms"
    expect(screen.getByText('Response time: 2.00 sec')).toBeInTheDocument();
    expect(screen.getByText('Tokens: 300')).toBeInTheDocument();
  });

  it('should handle single source correctly', () => {
    render(<ResponseInfo sourcesUsed={['ROC']} />);
    
    expect(screen.getByText('ROC')).toBeInTheDocument();
  });

  it('should handle only response time without token count', () => {
    render(<ResponseInfo responseTimeMs={1000} />);
    
    // Updated: format is now "{seconds} sec" instead of "{ms}ms"
    expect(screen.getByText('Response time: 1.00 sec')).toBeInTheDocument();
    expect(screen.queryByText(/Tokens:/)).not.toBeInTheDocument();
  });

  it('should handle only token count without response time', () => {
    render(<ResponseInfo tokenCount={150} />);
    
    expect(screen.getByText('Tokens: 150')).toBeInTheDocument();
    expect(screen.queryByText(/Response time:/)).not.toBeInTheDocument();
  });

  it('should have correct accessibility attributes', () => {
    render(<ResponseInfo sourcesUsed={['ROC']} />);
    
    const button = screen.getByTestId('button');
    expect(button).toHaveAttribute('aria-label', 'Response information');
  });

  it('should handle empty string in sources array', () => {
    render(<ResponseInfo sourcesUsed={['ROC', '', 'DIANA']} />);
    
    expect(screen.getByText('ROC, , DIANA')).toBeInTheDocument();
  });

  it('should handle zero values for metadata', () => {
    render(<ResponseInfo responseTimeMs={0} tokenCount={0} />);
    
    // Zero values are falsy, so the component won't render
    const { container } = render(<ResponseInfo responseTimeMs={0} tokenCount={0} />);
    expect(container.firstChild).toBeNull();
  });

  it('should render agent mode section when isAgentMode is true', () => {
    render(<ResponseInfo isAgentMode={true} />);
    
    expect(screen.getByText('Agent Mode')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  it('should render all sections together including agent mode', () => {
    render(
      <ResponseInfo
        sourcesUsed={['ROC']}
        responseTimeMs={1500}
        tokenCount={100}
        displayName="gpt-4o"
        isAgentMode={true}
      />
    );

    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('Performance')).toBeInTheDocument();
    expect(screen.getByText('Model')).toBeInTheDocument();
    expect(screen.getByText('Agent Mode')).toBeInTheDocument();
  });
});
