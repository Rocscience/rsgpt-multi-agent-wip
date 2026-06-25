'use client';

import { create } from 'zustand';

interface AgentModeState {
  isAgentMode: boolean;
  isWebSearch: boolean;
  setIsAgentMode: (isAgentMode: boolean) => void;
  setIsWebSearch: (isWebSearch: boolean) => void;
  toggleAgentMode: () => void;
  clear: () => void;
}

export const useAgentMode = create<AgentModeState>((set) => ({
  isAgentMode: false,
  isWebSearch: false,
  setIsAgentMode: (isAgentMode: boolean) => set({ isAgentMode }),
  setIsWebSearch: (isWebSearch: boolean) => set({ isWebSearch }),
  toggleAgentMode: () => set((state) => ({ isAgentMode: !state.isAgentMode })),
  clear: () => set({ isAgentMode: false, isWebSearch: false }),
}));

// Export clear function for store-utils
export const clearAgentMode = () => {
  useAgentMode.getState().clear();
};
