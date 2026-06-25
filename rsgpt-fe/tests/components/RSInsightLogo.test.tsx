import { render, screen } from '@testing-library/react';
import { RSInsightLogo } from '@/components/dashboard/rsinsight-logo';

describe('RSInsightLogo', () => {
  describe('Full variant (default)', () => {
    it('should render full logo by default', () => {
      const { container } = render(<RSInsightLogo />);
      
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveAttribute('viewBox', '0 0 4143 1080');
    });

    it('should render full logo when variant is explicitly set', () => {
      const { container } = render(<RSInsightLogo variant="full" />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('viewBox', '0 0 4143 1080');
    });

    it('should apply custom className', () => {
      const { container } = render(<RSInsightLogo className="custom-class" />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('custom-class');
    });

    it('should use default text color', () => {
      const { container } = render(<RSInsightLogo />);
      
      const textPaths = container.querySelectorAll('path[fill="currentColor"]');
      expect(textPaths.length).toBeGreaterThan(0);
    });

    it('should use custom text color', () => {
      const { container } = render(<RSInsightLogo textColor="#123456" />);
      
      const textPaths = container.querySelectorAll('path[fill="#123456"]');
      expect(textPaths.length).toBeGreaterThan(0);
    });

    it('should use default accent color', () => {
      const { container } = render(<RSInsightLogo />);
      
      const accentPaths = container.querySelectorAll('path[fill="#e35205"]');
      expect(accentPaths.length).toBeGreaterThan(0);
    });

    it('should use custom accent color', () => {
      const { container } = render(<RSInsightLogo accentColor="#ff0000" />);
      
      const accentPaths = container.querySelectorAll('path[fill="#ff0000"]');
      expect(accentPaths.length).toBeGreaterThan(0);
    });

    it('should contain both text and logo elements', () => {
      const { container } = render(<RSInsightLogo />);
      
      const allPaths = container.querySelectorAll('path');
      expect(allPaths.length).toBeGreaterThan(5); // Should have multiple paths for text and logo
    });
  });

  describe('Mark variant', () => {
    it('should render mark logo when variant is mark', () => {
      const { container } = render(<RSInsightLogo variant="mark" />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('viewBox', '0 0 1080 1080');
    });

    it('should apply custom className to mark variant', () => {
      const { container } = render(<RSInsightLogo variant="mark" className="mark-class" />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('mark-class');
    });

    it('should use custom accent color for mark variant', () => {
      const { container } = render(<RSInsightLogo variant="mark" accentColor="#00ff00" />);
      
      const accentPaths = container.querySelectorAll('path[fill="#00ff00"]');
      expect(accentPaths.length).toBe(2); // Mark should have exactly 2 paths
    });

    it('should only contain logo elements (no text)', () => {
      const { container } = render(<RSInsightLogo variant="mark" />);
      
      const allPaths = container.querySelectorAll('path');
      expect(allPaths.length).toBe(2); // Mark should have exactly 2 paths
    });

    it('should ignore textColor prop for mark variant', () => {
      const { container } = render(<RSInsightLogo variant="mark" textColor="#123456" />);
      
      // Mark variant should not have any paths with the text color
      const textPaths = container.querySelectorAll('path[fill="#123456"]');
      expect(textPaths.length).toBe(0);
    });
  });

  describe('Props combinations', () => {
    it('should handle all props together for full variant', () => {
      const { container } = render(
        <RSInsightLogo 
          variant="full"
          className="test-class"
          textColor="#111111"
          accentColor="#222222"
        />
      );
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('test-class');
      expect(svg).toHaveAttribute('viewBox', '0 0 4143 1080');
      
      const textPaths = container.querySelectorAll('path[fill="#111111"]');
      expect(textPaths.length).toBeGreaterThan(0);
      
      const accentPaths = container.querySelectorAll('path[fill="#222222"]');
      expect(accentPaths.length).toBeGreaterThan(0);
    });

    it('should handle all props together for mark variant', () => {
      const { container } = render(
        <RSInsightLogo 
          variant="mark"
          className="mark-test-class"
          textColor="#333333" // Should be ignored
          accentColor="#444444"
        />
      );
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveClass('mark-test-class');
      expect(svg).toHaveAttribute('viewBox', '0 0 1080 1080');
      
      const accentPaths = container.querySelectorAll('path[fill="#444444"]');
      expect(accentPaths.length).toBe(2);
      
      // Should not have text color paths
      const textPaths = container.querySelectorAll('path[fill="#333333"]');
      expect(textPaths.length).toBe(0);
    });
  });

  describe('SVG structure', () => {
    it('should have proper SVG namespace', () => {
      const { container } = render(<RSInsightLogo />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('xmlns', 'http://www.w3.org/2000/svg');
    });

    it('should be scalable vector graphics', () => {
      const { container } = render(<RSInsightLogo />);
      
      const svg = container.querySelector('svg');
      expect(svg?.tagName).toBe('svg');
    });

    it('should maintain aspect ratio', () => {
      const { container } = render(<RSInsightLogo variant="mark" />);
      
      const svg = container.querySelector('svg');
      const viewBox = svg?.getAttribute('viewBox');
      expect(viewBox).toBe('0 0 1080 1080'); // Square aspect ratio for mark
    });
  });

  describe('Accessibility', () => {
    it('should be accessible to screen readers', () => {
      const { container } = render(<RSInsightLogo />);
      
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('should work with custom aria attributes', () => {
      const { container } = render(<RSInsightLogo aria-label="RSInsight Company Logo" />);
      
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-label', 'RSInsight Company Logo');
    });
  });
});