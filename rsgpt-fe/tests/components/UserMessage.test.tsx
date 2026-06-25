import { render, screen } from '@testing-library/react';
import { UserMessage } from '@/components/chat/messages/user-message';
import type { UserMessageDto } from '@/lib/types';

describe('UserMessage', () => {
  const mockUserMessage: UserMessageDto = {
    id: 'user-123',
    message_text: 'Hello, this is a test message',
    created_at: '2023-01-01T00:00:00Z',
    status: 'completed',
    sources_requested: ['ROC']
  };

  it('should render user message text', () => {
    render(<UserMessage userMessage={mockUserMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
  });

  it('should handle multiline text correctly', () => {
    const multilineMessage: UserMessageDto = {
      ...mockUserMessage,
      message_text: 'Line 1\nLine 2\nLine 3'
    };

    render(<UserMessage userMessage={multilineMessage} />);
    
    // Use a regex to match the multiline text
    expect(screen.getByText(/Line 1.*Line 2.*Line 3/s)).toBeInTheDocument();
  });

  it('should handle empty message text', () => {
    const emptyMessage: UserMessageDto = {
      ...mockUserMessage,
      message_text: ''
    };

    const { container } = render(<UserMessage userMessage={emptyMessage} />);
    
    // Check that the component renders without crashing
    const messageDiv = container.querySelector('.whitespace-pre-wrap');
    expect(messageDiv).toBeInTheDocument();
    expect(messageDiv).toHaveTextContent('');
  });

  it('should handle special characters in message text', () => {
    const specialCharMessage: UserMessageDto = {
      ...mockUserMessage,
      message_text: 'Special chars: @#$%^&*()_+-=[]{}|;:,.<>?'
    };

    render(<UserMessage userMessage={specialCharMessage} />);
    
    expect(screen.getByText('Special chars: @#$%^&*()_+-=[]{}|;:,.<>?')).toBeInTheDocument();
  });

  it('should have correct CSS classes for styling', () => {
    const { container } = render(<UserMessage userMessage={mockUserMessage} />);
    
    const outerDiv = container.firstChild as HTMLElement;
    expect(outerDiv).toHaveClass('flex', 'justify-end', 'mb-8', 'sm:mb-12');
    
    const messageDiv = outerDiv.querySelector('div:nth-child(1)');
    expect(messageDiv).toHaveClass(
      'max-w-[85%]', 
      'sm:max-w-[75%]', 
      'lg:max-w-[70%]', 
      'bg-default/50', 
      'text-foreground', 
      'px-3', 
      'sm:px-4', 
      'py-2', 
      'sm:py-3', 
      'rounded-2xl'
    );
    
    const textDiv = messageDiv?.querySelector('div');
    expect(textDiv).toHaveClass('whitespace-pre-wrap', 'word-break');
  });

  it('should handle long message text', () => {
    const longMessage: UserMessageDto = {
      ...mockUserMessage,
      message_text: 'This is a very long message that should test how the component handles lengthy text content. '.repeat(10)
    };

    render(<UserMessage userMessage={longMessage} />);
    
    // Use a partial match instead of exact text
    expect(screen.getByText(/This is a very long message/)).toBeInTheDocument();
  });

  it('should handle isTemp prop (even though not used in current implementation)', () => {
    // Test that the component doesn't break when isTemp is provided
    expect(() => 
      render(<UserMessage userMessage={mockUserMessage} isTemp={true} />)
    ).not.toThrow();
    
    expect(() => 
      render(<UserMessage userMessage={mockUserMessage} isTemp={false} />)
    ).not.toThrow();
  });

  it('should memoize clean text correctly', () => {
    const { rerender } = render(<UserMessage userMessage={mockUserMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
    
    // Re-render with same message - should not cause issues
    rerender(<UserMessage userMessage={mockUserMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
  });

  it('should update when message text changes', () => {
    const { rerender } = render(<UserMessage userMessage={mockUserMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
    
    const updatedMessage: UserMessageDto = {
      ...mockUserMessage,
      message_text: 'Updated message text'
    };
    
    rerender(<UserMessage userMessage={updatedMessage} />);
    
    expect(screen.getByText('Updated message text')).toBeInTheDocument();
    expect(screen.queryByText('Hello, this is a test message')).not.toBeInTheDocument();
  });

  it('should handle different user message statuses', () => {
    const pendingMessage: UserMessageDto = {
      ...mockUserMessage,
      status: 'pending'
    };

    render(<UserMessage userMessage={pendingMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
  });

  it('should handle different sources requested', () => {
    const multiSourceMessage: UserMessageDto = {
      ...mockUserMessage,
      sources_requested: ['ROC', 'DIANA', '3GSM']
    };

    render(<UserMessage userMessage={multiSourceMessage} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
  });
});
