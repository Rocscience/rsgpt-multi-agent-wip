import { renderHook, act } from '@testing-library/react';
import { usePendingFirstMessage, clearPendingMessage } from '@/hooks/usePendingFirstMessage';
import { ModelName } from '@/lib/types';

describe('usePendingFirstMessage', () => {
  beforeEach(() => {
    // Clear the store before each test
    clearPendingMessage();
  });

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    expect(result.current.text).toBe('');
    expect(result.current.sources).toEqual([]);
    expect(result.current.selectedModel).toBeUndefined();
  });

  it('should set pending message with text and sources', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    act(() => {
      result.current.set({
        text: 'Hello world',
        sources: ['ROC', 'DIANA'],
        selectedModel: ModelName.GPT4O
      });
    });
    
    expect(result.current.text).toBe('Hello world');
    expect(result.current.sources).toEqual(['ROC', 'DIANA']);
    expect(result.current.selectedModel).toBe(ModelName.GPT4O);
  });

  it('should set pending message without selectedModel', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    act(() => {
      result.current.set({
        text: 'Test message',
        sources: ['ROC']
      });
    });
    
    expect(result.current.text).toBe('Test message');
    expect(result.current.sources).toEqual(['ROC']);
    expect(result.current.selectedModel).toBeUndefined();
  });

  it('should clear pending message', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    // Set some data first
    act(() => {
      result.current.set({
        text: 'Test message',
        sources: ['ROC', 'DIANA'],
        selectedModel: ModelName.GPT5
      });
    });
    
    expect(result.current.text).toBe('Test message');
    
    // Clear the data
    act(() => {
      result.current.clear();
    });
    
    expect(result.current.text).toBe('');
    expect(result.current.sources).toEqual([]);
    expect(result.current.selectedModel).toBeUndefined();
  });

  it('should persist state across hook instances', () => {
    // First hook instance
    const { result: result1 } = renderHook(() => usePendingFirstMessage());
    
    act(() => {
      result1.current.set({
        text: 'Persistent message',
        sources: ['ROC'],
        selectedModel: ModelName.GPT4OMINI
      });
    });
    
    // Second hook instance should have the same values
    const { result: result2 } = renderHook(() => usePendingFirstMessage());
    
    expect(result2.current.text).toBe('Persistent message');
    expect(result2.current.sources).toEqual(['ROC']);
    expect(result2.current.selectedModel).toBe(ModelName.GPT4OMINI);
  });

  it('should handle empty sources array', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    act(() => {
      result.current.set({
        text: 'Message with no sources',
        sources: []
      });
    });
    
    expect(result.current.text).toBe('Message with no sources');
    expect(result.current.sources).toEqual([]);
  });

  it('should handle multiple sources', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    act(() => {
      result.current.set({
        text: 'Multi-source message',
        sources: ['ROC', 'DIANA', 'CUSTOM']
      });
    });
    
    expect(result.current.sources).toEqual(['ROC', 'DIANA', 'CUSTOM']);
  });

  it('should handle clearPendingMessage function', () => {
    const { result } = renderHook(() => usePendingFirstMessage());
    
    // Set some data
    act(() => {
      result.current.set({
        text: 'Test',
        sources: ['ROC'],
        selectedModel: ModelName.GPT4_1
      });
    });
    
    expect(result.current.text).toBe('Test');
    
    // Clear using external function
    act(() => {
      clearPendingMessage();
    });
    
    // Re-render to get updated state
    const { result: newResult } = renderHook(() => usePendingFirstMessage());
    expect(newResult.current.text).toBe('');
    expect(newResult.current.sources).toEqual([]);
    expect(newResult.current.selectedModel).toBeUndefined();
  });
});
