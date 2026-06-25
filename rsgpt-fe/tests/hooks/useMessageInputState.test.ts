import { renderHook, act } from '@testing-library/react';
import { useMessageInputState, clearMessageInputState } from '@/hooks/useMessageInputState';

describe('useMessageInputState', () => {
  beforeEach(() => {
    // Clear the store before each test
    clearMessageInputState();
  });

  it('should initialize with default state', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    expect(result.current.position).toBe('center');
    expect(result.current.disabled).toBe(false);
    expect(result.current.onSubmit).toBeNull();
    expect(result.current.clearTextTrigger).toBe(0);
    expect(result.current.initialText).toBe('');
    expect(result.current.shouldAutoSend).toBe(false);
  });

  it('should set position', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    act(() => {
      result.current.setPosition('bottom');
    });
    
    expect(result.current.position).toBe('bottom');
    
    act(() => {
      result.current.setPosition('hidden');
    });
    
    expect(result.current.position).toBe('hidden');
  });

  it('should set disabled state', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    act(() => {
      result.current.setDisabled(true);
    });
    
    expect(result.current.disabled).toBe(true);
    
    act(() => {
      result.current.setDisabled(false);
    });
    
    expect(result.current.disabled).toBe(false);
  });

  it('should set onSubmit callback', () => {
    const { result } = renderHook(() => useMessageInputState());
    const mockOnSubmit = jest.fn();
    
    act(() => {
      result.current.setOnSubmit(mockOnSubmit);
    });
    
    expect(result.current.onSubmit).toBe(mockOnSubmit);
  });

  it('should increment clearTextTrigger when clearText is called', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    expect(result.current.clearTextTrigger).toBe(0);
    
    act(() => {
      result.current.clearText();
    });
    
    expect(result.current.clearTextTrigger).toBe(1);
    
    act(() => {
      result.current.clearText();
    });
    
    expect(result.current.clearTextTrigger).toBe(2);
  });

  it('should set initial text and trigger auto-send', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    act(() => {
      result.current.setInitialText('Hello world');
    });
    
    expect(result.current.initialText).toBe('Hello world');
    expect(result.current.shouldAutoSend).toBe(true);
  });

  it('should trigger auto-send', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    expect(result.current.shouldAutoSend).toBe(false);
    
    act(() => {
      result.current.triggerAutoSend();
    });
    
    expect(result.current.shouldAutoSend).toBe(true);
  });

  it('should clear all state', () => {
    const { result } = renderHook(() => useMessageInputState());
    const mockOnSubmit = jest.fn();
    
    // Set some state first
    act(() => {
      result.current.setPosition('bottom');
      result.current.setDisabled(true);
      result.current.setOnSubmit(mockOnSubmit);
      result.current.clearText();
      result.current.setInitialText('Test text');
    });
    
    expect(result.current.position).toBe('bottom');
    expect(result.current.disabled).toBe(true);
    expect(result.current.onSubmit).toBe(mockOnSubmit);
    expect(result.current.clearTextTrigger).toBe(1);
    expect(result.current.initialText).toBe('Test text');
    expect(result.current.shouldAutoSend).toBe(true);
    
    // Clear all state
    act(() => {
      result.current.clear();
    });
    
    expect(result.current.position).toBe('center');
    expect(result.current.disabled).toBe(false);
    expect(result.current.onSubmit).toBeNull();
    expect(result.current.clearTextTrigger).toBe(0);
    expect(result.current.initialText).toBe('');
    expect(result.current.shouldAutoSend).toBe(false);
  });

  it('should persist state across hook instances', () => {
    // First hook instance
    const { result: result1 } = renderHook(() => useMessageInputState());
    
    act(() => {
      result1.current.setPosition('bottom');
      result1.current.setDisabled(true);
    });
    
    // Second hook instance should have the same values
    const { result: result2 } = renderHook(() => useMessageInputState());
    
    expect(result2.current.position).toBe('bottom');
    expect(result2.current.disabled).toBe(true);
  });

  it('should handle clearMessageInputState function', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    // Set some state
    act(() => {
      result.current.setPosition('hidden');
      result.current.setDisabled(true);
    });
    
    expect(result.current.position).toBe('hidden');
    expect(result.current.disabled).toBe(true);
    
    // Clear using external function
    act(() => {
      clearMessageInputState();
    });
    
    // Re-render to get updated state
    const { result: newResult } = renderHook(() => useMessageInputState());
    expect(newResult.current.position).toBe('center');
    expect(newResult.current.disabled).toBe(false);
  });

  it('should handle multiple clearText calls correctly', () => {
    const { result } = renderHook(() => useMessageInputState());
    
    const initialTrigger = result.current.clearTextTrigger;
    
    act(() => {
      result.current.clearText();
      result.current.clearText();
      result.current.clearText();
    });
    
    expect(result.current.clearTextTrigger).toBe(initialTrigger + 3);
  });
});
