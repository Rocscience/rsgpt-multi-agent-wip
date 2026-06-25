import { renderHook, act } from '@testing-library/react';
import { useNavigationState } from '@/hooks/useNavigationState';

describe('useNavigationState', () => {
  it('should initialize with default state', () => {
    const { result } = renderHook(() => useNavigationState());
    
    expect(result.current.isNavigating).toBe(false);
    expect(result.current.targetSessionId).toBeNull();
  });

  it('should set navigation state with session ID', () => {
    const { result } = renderHook(() => useNavigationState());
    
    act(() => {
      result.current.setNavigating(true, 'session-123');
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBe('session-123');
  });

  it('should set navigation state without session ID', () => {
    const { result } = renderHook(() => useNavigationState());
    
    act(() => {
      result.current.setNavigating(true);
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBeNull();
  });

  it('should clear navigation state', () => {
    const { result } = renderHook(() => useNavigationState());
    
    // Set navigation state first
    act(() => {
      result.current.setNavigating(true, 'session-456');
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBe('session-456');
    
    // Clear navigation state
    act(() => {
      result.current.setNavigating(false);
    });
    
    expect(result.current.isNavigating).toBe(false);
    expect(result.current.targetSessionId).toBeNull();
  });

  it('should update session ID while navigating', () => {
    const { result } = renderHook(() => useNavigationState());
    
    act(() => {
      result.current.setNavigating(true, 'session-1');
    });
    
    expect(result.current.targetSessionId).toBe('session-1');
    
    act(() => {
      result.current.setNavigating(true, 'session-2');
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBe('session-2');
  });

  it('should handle explicit null session ID', () => {
    const { result } = renderHook(() => useNavigationState());
    
    act(() => {
      result.current.setNavigating(true, null);
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBeNull();
  });

  it('should persist state across hook instances', () => {
    // First hook instance
    const { result: result1 } = renderHook(() => useNavigationState());
    
    act(() => {
      result1.current.setNavigating(true, 'persistent-session');
    });
    
    // Second hook instance should have the same values
    const { result: result2 } = renderHook(() => useNavigationState());
    
    expect(result2.current.isNavigating).toBe(true);
    expect(result2.current.targetSessionId).toBe('persistent-session');
  });

  it('should handle rapid state changes', () => {
    const { result } = renderHook(() => useNavigationState());
    
    act(() => {
      result.current.setNavigating(true, 'session-1');
      result.current.setNavigating(false);
      result.current.setNavigating(true, 'session-2');
    });
    
    expect(result.current.isNavigating).toBe(true);
    expect(result.current.targetSessionId).toBe('session-2');
  });

  it('should maintain referential stability of setNavigating', () => {
    const { result, rerender } = renderHook(() => useNavigationState());
    
    const initialSetter = result.current.setNavigating;
    
    // Trigger a re-render
    rerender();
    
    expect(result.current.setNavigating).toBe(initialSetter);
  });
});
