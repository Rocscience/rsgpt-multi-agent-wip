import { render, screen, fireEvent } from '@testing-library/react';
import { SourceSelector } from '@/components/chat/input/message-input-components/source-selector';

// Mock next-themes
jest.mock('next-themes', () => ({
  useTheme: jest.fn(() => ({ theme: 'light' }))
}));

// Mock HeroUI components - Updated to use Dropdown instead of Select
jest.mock('@heroui/react', () => ({
  Dropdown: ({ children, placement, isOpen, onOpenChange, ...props }: any) => (
    <div data-testid="source-selector" data-placement={placement}>
      {children}
    </div>
  ),
  DropdownTrigger: ({ children }: any) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
  DropdownMenu: ({ children, onAction, closeOnSelect, ...props }: any) => (
    <div data-testid="dropdown-menu" data-close-on-select={closeOnSelect}>
      {typeof children === 'function' ? children : children}
    </div>
  ),
  DropdownItem: ({ children, key, startContent, endContent, ...props }: any) => (
    <div data-testid="dropdown-item" data-key={key}>
      {startContent}
      {children}
      {endContent}
    </div>
  ),
  Button: ({ children, isDisabled, 'aria-label': ariaLabel, ...props }: any) => (
    <button 
      data-testid="source-button" 
      disabled={isDisabled} 
      aria-label={ariaLabel}
    >
      {children}
    </button>
  ),
  Tooltip: ({ children, content }: any) => (
    <div data-testid="tooltip" title={content}>
      {children}
    </div>
  )
}));

// Mock SourceLogos - Updated to include AQUANTY
jest.mock('@/components/chat/input/message-input-components/source-logos', () => ({
  SOURCE_LOGO_COMPONENTS: {
    ROC: ({ className, style }: any) => <div data-testid="roc-logo" className={className} style={style}>ROC Logo</div>,
    DIANA: ({ className, style }: any) => <div data-testid="diana-logo" className={className} style={style}>DIANA Logo</div>,
    '3GSM': ({ className, style }: any) => <div data-testid="3gsm-logo" className={className} style={style}>3GSM Logo</div>,
    '2SI': ({ className, style }: any) => <div data-testid="2si-logo" className={className} style={style}>2SI Logo</div>,
    'ROCKFIELD': ({ className, style }: any) => <div data-testid="rockfield-logo" className={className} style={style}>ROCKFIELD Logo</div>,
    'AQUANTY': ({ className, style }: any) => <div data-testid="aquanty-logo" className={className} style={style}>AQUANTY Logo</div>
  }
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/solid', () => ({
  CheckIcon: (props: any) => <span data-testid="check-icon" {...props} />
}));

import { useTheme } from 'next-themes';

describe('SourceSelector', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useTheme as jest.Mock).mockReturnValue({ theme: 'light' });
  });

  it('should render the source selector', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} />);
    
    expect(screen.getByTestId('source-selector')).toBeInTheDocument();
    // Tooltip content now shows "Sources: Rocscience" format
    expect(screen.getByTestId('tooltip')).toHaveAttribute('title', 'Sources: Rocscience');
  });

  it('should render all source dropdown items', () => {
    render(<SourceSelector selected={[]} onChange={mockOnChange} />);
    
    const dropdownItems = screen.getAllByTestId('dropdown-item');
    expect(dropdownItems).toHaveLength(6); // ROC, DIANA, 3GSM, 2SI, ROCKFIELD, AQUANTY
  });

  it('should render selected logos in the trigger', () => {
    render(<SourceSelector selected={['ROC', 'DIANA']} onChange={mockOnChange} />);
    
    const trigger = screen.getByTestId('dropdown-trigger');
    expect(trigger).toBeInTheDocument();
    
    // Should render logos for selected sources (multiple instances exist - one in trigger, one in dropdown)
    const rocLogos = screen.getAllByTestId('roc-logo');
    const dianaLogos = screen.getAllByTestId('diana-logo');
    expect(rocLogos.length).toBeGreaterThanOrEqual(1);
    expect(dianaLogos.length).toBeGreaterThanOrEqual(1);
  });

  it('should render single logo when only one source is selected', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} />);
    
    // Only ROC logo should be visible in trigger area (excluding dropdown items)
    const trigger = screen.getByTestId('dropdown-trigger');
    expect(trigger.querySelector('[data-testid="roc-logo"]')).toBeInTheDocument();
  });

  it('should render stacked logos when multiple sources are selected', () => {
    render(<SourceSelector selected={['ROC', 'DIANA', '3GSM']} onChange={mockOnChange} />);
    
    const trigger = screen.getByTestId('dropdown-trigger');
    expect(trigger.querySelector('[data-testid="roc-logo"]')).toBeInTheDocument();
    expect(trigger.querySelector('[data-testid="diana-logo"]')).toBeInTheDocument();
    expect(trigger.querySelector('[data-testid="3gsm-logo"]')).toBeInTheDocument();
  });

  it('should show all company names in dropdown items', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} />);
    
    // Check that company names are rendered in dropdown items
    expect(screen.getByText('Rocscience')).toBeInTheDocument();
    expect(screen.getByText('DIANA')).toBeInTheDocument();
    expect(screen.getByText('3GSM')).toBeInTheDocument();
    expect(screen.getByText('2Si')).toBeInTheDocument();
    expect(screen.getByText('Rockfield')).toBeInTheDocument();
    expect(screen.getByText('Aquanty')).toBeInTheDocument();
  });

  it('should disable selector when readOnly is true', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} readOnly />);
    
    const button = screen.getByTestId('source-button');
    expect(button).toBeDisabled();
  });

  it('should have correct tooltip content for multiple sources', () => {
    render(<SourceSelector selected={['ROC', 'DIANA']} onChange={mockOnChange} />);
    
    const tooltip = screen.getByTestId('tooltip');
    expect(tooltip).toHaveAttribute('title', 'Sources: Rocscience, DIANA');
  });

  it('should render all 6 sources including AQUANTY', () => {
    render(<SourceSelector selected={['AQUANTY']} onChange={mockOnChange} />);
    
    // AQUANTY should be selectable
    expect(screen.getByText('Aquanty')).toBeInTheDocument();
  });

  it('should apply closeOnSelect={false} to dropdown menu', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} />);
    
    const dropdownMenu = screen.getByTestId('dropdown-menu');
    expect(dropdownMenu).toHaveAttribute('data-close-on-select', 'false');
  });

  it('should show max 4 logos plus counter when more than 4 sources selected', () => {
    render(<SourceSelector selected={['ROC', 'DIANA', '3GSM', '2SI', 'ROCKFIELD']} onChange={mockOnChange} />);
    
    // Should show +1 counter for the 5th source
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('should render button with correct aria-label', () => {
    render(<SourceSelector selected={['ROC']} onChange={mockOnChange} />);
    
    const button = screen.getByTestId('source-button');
    expect(button).toHaveAttribute('aria-label', 'Source selector');
  });
});
