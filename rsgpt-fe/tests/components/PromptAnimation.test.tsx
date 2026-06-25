import { render, screen, fireEvent } from '@testing-library/react';
import PromptAnimation from '@/components/dashboard/prompt-animation';

// Mock the useUser hook
jest.mock('@auth0/nextjs-auth0', () => ({
  useUser: jest.fn(() => ({
    user: { sub: 'test-user', name: 'Test User' },
    isLoading: false
  }))
}));

// Mock framer-motion
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>
  },
  useMotionValue: jest.fn(() => ({ set: jest.fn() }))
}));

// Mock HeroUI components
jest.mock('@heroui/react', () => ({
  Card: ({ children, className, onPress, isPressable, isHoverable, ...props }: any) => (
    <div 
      className={className} 
      onClick={onPress}
      data-pressable={isPressable}
      data-hoverable={isHoverable}
      data-testid="prompt-card" 
      {...props}
    >
      {children}
    </div>
  ),
  CardBody: ({ children, className }: any) => (
    <div className={className}>{children}</div>
  )
}));

describe('PromptAnimation', () => {

  describe('Basic Rendering', () => {
    it('should render without crashing', () => {
      const { container } = render(<PromptAnimation />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should render prompt cards', () => {
      render(<PromptAnimation />);
      const promptCards = screen.getAllByTestId('prompt-card');
      expect(promptCards.length).toBeGreaterThan(0);
    });

    it('should have correct container structure', () => {
      const { container } = render(<PromptAnimation />);
      const mainDiv = container.querySelector('.w-full.overflow-hidden.py-8.bg-secondary');
      expect(mainDiv).toBeInTheDocument();
    });
  });

  describe('Prompt Content', () => {
    it('should display prompt text', () => {
      render(<PromptAnimation />);
      
      // Check for actual prompt text that's rendered (using getAllByText since there are multiple rows)
      expect(screen.getAllByText(/How do I model anisotropic materials in Slide2/)[0]).toBeInTheDocument();
      expect(screen.getAllByText(/How to create a bond-slip reinforcement in DIANA/)[0]).toBeInTheDocument();
    });

    it('should display various prompt cards', () => {
      render(<PromptAnimation />);
      
      // Check for different types of prompts (using getAllByText since there are multiple rows)
      expect(screen.getAllByText(/Does RSLog offer customization/)[0]).toBeInTheDocument();
      expect(screen.getAllByText(/Can RSWall design for different wall types/)[0]).toBeInTheDocument();
    });
  });

  describe('Basic Interactions', () => {
    it('should handle card clicks', () => {
      render(<PromptAnimation />);
      
      const firstCard = screen.getAllByTestId('prompt-card')[0];
      fireEvent.click(firstCard);
      
      // Just verify the click doesn't crash
      expect(firstCard).toBeInTheDocument();
    });
  });

  describe('Layout', () => {
    it('should render multiple rows of prompts', () => {
      const { container } = render(<PromptAnimation />);
      
      // The component should render multiple motion divs for different rows
      const mainDiv = container.querySelector('.w-full.overflow-hidden.py-8.bg-secondary');
      expect(mainDiv?.children.length).toBeGreaterThan(0);
    });
  });
});