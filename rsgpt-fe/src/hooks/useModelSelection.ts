'use client';

import { create } from 'zustand';
import { ModelName, ReasoningLevel } from '@/lib/types';

interface ModelSelectionState {
  selectedModel: ModelName;
  reasoningLevel: ReasoningLevel;
  setSelectedModel: (model: ModelName) => void;
  setReasoningLevel: (level: ReasoningLevel) => void;
  clear: () => void;
}

export const useModelSelection = create<ModelSelectionState>((set) => ({
  selectedModel: ModelName.CLAUDE_HAIKU_4_5, // Default model (Claude Haiku 4.5)
  reasoningLevel: ReasoningLevel.MEDIUM, // Default reasoning level for Haiku
  setSelectedModel: (model: ModelName) => set({ selectedModel: model }),
  setReasoningLevel: (level: ReasoningLevel) => set({ reasoningLevel: level }),
  clear: () => set({
    selectedModel: ModelName.CLAUDE_HAIKU_4_5,
    reasoningLevel: ReasoningLevel.MEDIUM
  }),
}));

// Export clear function for store-utils
export const clearModelSelection = () => {
  useModelSelection.getState().clear();
};
