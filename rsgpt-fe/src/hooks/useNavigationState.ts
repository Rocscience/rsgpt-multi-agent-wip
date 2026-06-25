'use client';

import { create } from 'zustand';
import { useSourceList } from './useSourceList';
import { useContextUsage } from './useContextUsage';

interface NavigationState {
  isNavigating: boolean;
  targetSessionId: string | null;
  setNavigating: (isNavigating: boolean, targetSessionId?: string | null) => void;
}

export const useNavigationState = create<NavigationState>((set) => ({
  isNavigating: false,
  targetSessionId: null,
  setNavigating: (isNavigating, targetSessionId = null) => {
    set({ isNavigating, targetSessionId });
    
    // Clear sources and context usage when navigating to a new chat
    if (isNavigating && targetSessionId === 'new') {
      useSourceList.getState().clearSources();
      useContextUsage.getState().clearContextUsage();
    }
  }
}));
