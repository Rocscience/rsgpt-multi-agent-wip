import { renderHook, act } from '@testing-library/react';
import { useModelSelection, clearModelSelection } from '@/hooks/useModelSelection';
import { ModelName } from '@/lib/types';

describe('useModelSelection', () => {
  beforeEach(() => {
    // Clear the store before each test
    clearModelSelection();
  });

  it('should initialize with default model', () => {
    const { result } = renderHook(() => useModelSelection());

    expect(result.current.selectedModel).toBe(ModelName.CLAUDE_HAIKU_4_5);
  });

  it('should update selected model', () => {
    const { result } = renderHook(() => useModelSelection());
    
    act(() => {
      result.current.setSelectedModel(ModelName.GPT4O);
    });
    
    expect(result.current.selectedModel).toBe(ModelName.GPT4O);
  });

  it('should persist model selection across hook instances', () => {
    // First hook instance
    const { result: result1 } = renderHook(() => useModelSelection());
    
    act(() => {
      result1.current.setSelectedModel(ModelName.GPT5);
    });
    
    // Second hook instance should have the same value
    const { result: result2 } = renderHook(() => useModelSelection());
    
    expect(result2.current.selectedModel).toBe(ModelName.GPT5);
  });

  it('should handle all model types', () => {
    const { result } = renderHook(() => useModelSelection());
    
    const modelTypes = [
      ModelName.GPT4O,
      ModelName.GPT4OMINI,
      ModelName.GPT4_1,
      ModelName.GPT5,
      ModelName.GPT5_MINI
    ];
    
    modelTypes.forEach(model => {
      act(() => {
        result.current.setSelectedModel(model);
      });
      
      expect(result.current.selectedModel).toBe(model);
    });
  });

  it('should clear model selection', () => {
    const { result } = renderHook(() => useModelSelection());
    
    // Set a non-default model
    act(() => {
      result.current.setSelectedModel(ModelName.GPT5);
    });
    
    expect(result.current.selectedModel).toBe(ModelName.GPT5);
    
    // Clear should reset to default
    act(() => {
      clearModelSelection();
    });
    
    // Re-render hook to get updated state
    const { result: newResult } = renderHook(() => useModelSelection());
    expect(newResult.current.selectedModel).toBe(ModelName.CLAUDE_HAIKU_4_5);
  });

  it('should maintain referential stability of setSelectedModel', () => {
    const { result, rerender } = renderHook(() => useModelSelection());
    
    const initialSetter = result.current.setSelectedModel;
    
    // Trigger a re-render
    rerender();
    
    expect(result.current.setSelectedModel).toBe(initialSetter);
  });

  it('should handle rapid model changes', () => {
    const { result } = renderHook(() => useModelSelection());
    
    act(() => {
      result.current.setSelectedModel(ModelName.GPT4O);
      result.current.setSelectedModel(ModelName.GPT5);
      result.current.setSelectedModel(ModelName.GPT4OMINI);
    });
    
    expect(result.current.selectedModel).toBe(ModelName.GPT4OMINI);
  });
});
