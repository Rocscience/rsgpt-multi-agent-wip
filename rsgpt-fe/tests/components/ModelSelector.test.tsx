import { render, screen, within } from '@testing-library/react';
import { ModelSelector } from '@/components/chat/input/message-input-components/model-selector';

// Mock the useModelSelection hook
const mockSetSelectedModel = jest.fn();
const mockSetReasoningLevel = jest.fn();
jest.mock('@/hooks/useModelSelection', () => ({
  useModelSelection: jest.fn(() => ({
    selectedModel: 'claude-haiku-4-5-20251001',
    reasoningLevel: 'low',
    setSelectedModel: mockSetSelectedModel,
    setReasoningLevel: mockSetReasoningLevel
  }))
}));

// Mock the useAgentMode hook
jest.mock('@/hooks/useAgentMode', () => ({
  useAgentMode: jest.fn(() => ({
    isAgentMode: false
  }))
}));

// Mock the types module with inline data
jest.mock('@/lib/types', () => {
  const ModelName = {
    GPT5_2: 'gpt-5.2-2025-12-11',
    CLAUDE_HAIKU_4_5: 'claude-haiku-4-5-20251001',
    XAI_GROK_4_1_FAST: 'grok-4-1-fast',
    GEMINI_3_FLASH: 'gemini-3-flash-preview',
  };

  const Provider = {
    OPENAI: 'openai',
    ANTHROPIC: 'anthropic',
    XAI: 'xai',
    PERPLEXITY: 'perplexity',
    GOOGLE: 'google',
  };

  const ModelMode = {
    AGENT: 'agent',
    REGULAR: 'regular',
    BOTH: 'both',
  };

  const ReasoningLevel = {
    NONE: 'none',
    LOW: 'low',
    MEDIUM: 'medium',
    HIGH: 'high',
  };

  const MODEL_CONFIGS = {
    [ModelName.CLAUDE_HAIKU_4_5]: {
      id: ModelName.CLAUDE_HAIKU_4_5,
      displayName: 'Claude Haiku 4.5',
      description: "Anthropic's fastest model with extended thinking capability.",
      provider: Provider.ANTHROPIC,
      model: 'claude-haiku-4-5-20251001',
      reasoning: ReasoningLevel.LOW,
      modes: [ModelMode.AGENT, ModelMode.REGULAR],
      max_input_tokens: 200000,
    },
    [ModelName.GPT5_2]: {
      id: ModelName.GPT5_2,
      displayName: 'GPT-5.2',
      description: "OpenAI's latest model with improved reasoning capabilities.",
      provider: Provider.OPENAI,
      model: 'gpt-5.2-2025-12-11',
      reasoning: ReasoningLevel.NONE,
      modes: [ModelMode.AGENT, ModelMode.REGULAR],
      max_input_tokens: 400000,
    },
    [ModelName.XAI_GROK_4_1_FAST]: {
      id: ModelName.XAI_GROK_4_1_FAST,
      displayName: 'xAI Grok 4.1 Fast',
      description: "xAI's fast model with optional reasoning capabilities.",
      provider: Provider.XAI,
      model: 'grok-4-1-fast',
      reasoning: ReasoningLevel.MEDIUM,
      modes: [ModelMode.AGENT],
      max_input_tokens: 350000,
    },
    [ModelName.GEMINI_3_FLASH]: {
      id: ModelName.GEMINI_3_FLASH,
      displayName: 'Gemini 3 Flash',
      description: "Google's frontier-class model with fast performance at reduced cost.",
      provider: Provider.GOOGLE,
      model: 'gemini-3-flash-preview',
      reasoning: ReasoningLevel.MEDIUM,
      modes: [ModelMode.AGENT, ModelMode.REGULAR],
      max_input_tokens: 1000000,
    },
  };

  const regularModeModels = [
    MODEL_CONFIGS[ModelName.CLAUDE_HAIKU_4_5],
    MODEL_CONFIGS[ModelName.GPT5_2],
    MODEL_CONFIGS[ModelName.GEMINI_3_FLASH],
  ];

  return {
    ModelName,
    Provider,
    ModelMode,
    ReasoningLevel,
    MODEL_CONFIGS,
    getAgentModeModels: jest.fn(() => Object.values(MODEL_CONFIGS)),
    getRegularModeModels: jest.fn(() => regularModeModels),
    REASONING_LEVEL_TO_EFFORT: {
      [ReasoningLevel.NONE]: 'none',
      [ReasoningLevel.LOW]: 'low',
      [ReasoningLevel.MEDIUM]: 'medium',
      [ReasoningLevel.HIGH]: 'high',
    },
  };
});

// Mock HeroUI components - use different testids for different button variants
jest.mock('@heroui/react', () => ({
  Button: ({ children, endContent, onPress, variant, ...props }: any) => {
    // Main model button has variant="light" and endContent (chevron icon)
    const testId = variant === 'light' && endContent ? 'model-button' : 'reasoning-button';
    return (
      <button onClick={onPress} variant={variant} {...props} data-testid={testId}>
        {children}
        {endContent}
      </button>
    );
  },
  Dropdown: ({ children, className }: any) => (
    <div className={className} data-testid="dropdown">{children}</div>
  ),
  DropdownTrigger: ({ children }: any) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
  DropdownMenu: ({ children, onSelectionChange, selectedKeys, selectionMode, ...props }: any) => (
    <div 
      data-testid="dropdown-menu" 
      data-selected-keys={JSON.stringify(selectedKeys)}
      data-on-selection-change={onSelectionChange ? 'true' : 'false'}
      data-selection-mode={selectionMode}
      {...props}
    >
      {children}
    </div>
  ),
  DropdownItem: ({ children, textValue, closeOnSelect, ...props }: any) => (
    <div {...props} data-testid="dropdown-item" data-text-value={textValue}>
      {children}
    </div>
  ),
  Tooltip: ({ children }: any) => <>{children}</>,
  ButtonGroup: ({ children, ...props }: any) => (
    <div data-testid="button-group" {...props}>{children}</div>
  ),
  Divider: (props: any) => <hr data-testid="divider" {...props} />
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  ChevronDownIcon: (props: any) => <div data-testid="chevron-icon" {...props} />
}));

import { useModelSelection } from '@/hooks/useModelSelection';
import { ModelName, ReasoningLevel } from '@/lib/types';

describe('ModelSelector', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render with default selected model', () => {
    render(<ModelSelector />);
    
    expect(screen.getByTestId('dropdown')).toBeInTheDocument();
    expect(screen.getByTestId('model-button')).toBeInTheDocument();
    
    // Check the button contains the selected model text (Claude Haiku 4.5)
    const button = screen.getByTestId('model-button');
    expect(button).toHaveTextContent('Claude Haiku 4.5');
  });

  it('should display correct model name for selected model', () => {
    (useModelSelection as unknown as jest.Mock<any>).mockReturnValue({
      selectedModel: ModelName.CLAUDE_HAIKU_4_5,
      reasoningLevel: ReasoningLevel.LOW,
      setSelectedModel: mockSetSelectedModel,
      setReasoningLevel: mockSetReasoningLevel
    });

    render(<ModelSelector />);
    
    const button = screen.getByTestId('model-button');
    expect(button).toHaveTextContent('Claude Haiku 4.5');
  });

  it('should render chevron down icon', () => {
    render(<ModelSelector />);
    
    expect(screen.getByTestId('chevron-icon')).toBeInTheDocument();
  });

  it('should render dropdown with bg-background class', () => {
    render(<ModelSelector />);
    
    const dropdown = screen.getByTestId('dropdown');
    expect(dropdown).toHaveClass('bg-background');
  });

  it('should render available models in dropdown menu', () => {
    render(<ModelSelector />);
    
    const dropdownItems = screen.getAllByTestId('dropdown-item');
    // Should have 3 models in regular mode (Claude Haiku 4.5, GPT-5.2, Gemini 3 Flash)
    expect(dropdownItems).toHaveLength(3);

    // Check that model display names are present in text values
    const textValues = dropdownItems.map(item => item.getAttribute('data-text-value'));
    expect(textValues).toContain('Claude Haiku 4.5');
    expect(textValues).toContain('GPT-5.2');
    expect(textValues).toContain('Gemini 3 Flash');
  });

  it('should have correct selected keys in dropdown menu', () => {
    render(<ModelSelector />);
    
    const dropdownMenu = screen.getByTestId('dropdown-menu');
    expect(dropdownMenu).toHaveAttribute('data-selected-keys', JSON.stringify([ModelName.CLAUDE_HAIKU_4_5]));
  });

  it('should have onSelectionChange handler set up', () => {
    render(<ModelSelector />);
    
    const dropdownMenu = screen.getByTestId('dropdown-menu');
    expect(dropdownMenu).toHaveAttribute('data-on-selection-change', 'true');
  });

  it('should not call setSelectedModel on initial render', () => {
    render(<ModelSelector />);
    
    // setSelectedModel should not be called on initial render when model is valid
    expect(mockSetSelectedModel).not.toHaveBeenCalled();
  });

  it('should handle different selected models correctly', () => {
    (useModelSelection as unknown as jest.Mock<any>).mockReturnValue({
      selectedModel: ModelName.GPT5_2,
      reasoningLevel: ReasoningLevel.NONE,
      setSelectedModel: mockSetSelectedModel,
      setReasoningLevel: mockSetReasoningLevel
    });

    render(<ModelSelector />);
    
    const button = screen.getByTestId('model-button');
    expect(button).toHaveTextContent('GPT-5.2');
  });

  it('should have correct button variant (light)', () => {
    render(<ModelSelector />);
    
    const button = screen.getByTestId('model-button');
    expect(button).toHaveAttribute('variant', 'light');
  });

  it('should have correct dropdown menu selection mode', () => {
    render(<ModelSelector />);
    
    const dropdownMenu = screen.getByTestId('dropdown-menu');
    expect(dropdownMenu).toHaveAttribute('data-selection-mode', 'single');
  });

  it('should render model text with truncate class', () => {
    render(<ModelSelector />);
    
    const button = screen.getByTestId('model-button');
    const modelText = button.querySelector('span');
    expect(modelText).toHaveClass('truncate');
    expect(modelText).toHaveClass('text-xs');
  });

  it('should render dividers between dropdown items', () => {
    render(<ModelSelector />);
    
    // Should have dividers between items (n-1 dividers for n items)
    const dividers = screen.getAllByTestId('divider');
    const dropdownItems = screen.getAllByTestId('dropdown-item');
    expect(dividers.length).toBe(dropdownItems.length - 1);
  });

  it('should fallback to default model when selected model is not available', () => {
    (useModelSelection as unknown as jest.Mock<any>).mockReturnValue({
      selectedModel: 'unknown-model',
      reasoningLevel: ReasoningLevel.NONE,
      setSelectedModel: mockSetSelectedModel,
      setReasoningLevel: mockSetReasoningLevel
    });

    render(<ModelSelector />);
    
    // When model is not in available models, it falls back to Claude Haiku 4.5
    const button = screen.getByTestId('model-button');
    expect(button).toHaveTextContent('Claude Haiku 4.5');
  });

  it('should render reasoning buttons for models that support reasoning', () => {
    render(<ModelSelector />);

    // Claude Haiku 4.5 (fallback from previous test's 'unknown-model') supports Anthropic reasoning (Low/Medium/High)
    const reasoningButtons = screen.getAllByTestId('reasoning-button');
    expect(reasoningButtons.length).toBeGreaterThan(0);
  });
});
