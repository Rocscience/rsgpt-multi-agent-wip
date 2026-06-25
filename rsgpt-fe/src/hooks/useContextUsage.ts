'use client';

import { create } from 'zustand';
import { MODEL_CONFIGS, ModelName } from '@/lib/types';

interface ContextUsageState {
  totalTokens: number;
  maxTokens: number;
  usagePercentage: number;
  modelName: string | null;
  sessionId: string | null;
  isVisible: boolean;
  baseTokens: number; // Actual input tokens including system instructions (for recalculation)
  updateContextUsage: (data: {
    session_id: string;
    total_tokens: number;
    max_tokens: number;
    usage_percentage: number;
    model_name: string;
  }) => void;
  setFromHistory: (current_tokens: number, model_name: string, session_id: string) => void;
  recalculateForModel: (model_name: string) => void;
  clearContextUsage: () => void;
  clear: () => void;
}

export const useContextUsage = create<ContextUsageState>((set, get) => ({
  totalTokens: 0,
  maxTokens: 0,
  usagePercentage: 0,
  modelName: null,
  sessionId: null,
  isVisible: false,
  baseTokens: 0,
  updateContextUsage: (data) => set({
    totalTokens: data.total_tokens,
    maxTokens: data.max_tokens,
    usagePercentage: data.usage_percentage,
    modelName: data.model_name,
    sessionId: data.session_id,
    isVisible: true,
    baseTokens: data.total_tokens, // Actual input tokens from backend (includes system instructions)
  }),
  setFromHistory: (current_tokens, model_name, session_id) => {
    // Look up max_tokens from MODEL_CONFIGS
    const modelConfig = MODEL_CONFIGS[model_name as ModelName];
    const max_tokens = modelConfig?.max_input_tokens || 200000; // Fallback to 200k
    
    // Calculate usage_percentage (current_tokens already includes system instructions from backend)
    const usage_percentage = max_tokens > 0 ? (current_tokens / max_tokens) * 100 : 0;
    
    set({
      totalTokens: current_tokens,
      maxTokens: max_tokens,
      usagePercentage: usage_percentage,
      modelName: model_name,
      sessionId: session_id,
      isVisible: true,
      baseTokens: current_tokens, // Store tokens for recalculation
    });
  },
  recalculateForModel: (model_name) => {
    const state = get();
    
    // Look up new max_input_tokens from MODEL_CONFIGS
    const modelConfig = MODEL_CONFIGS[model_name as ModelName];
    const new_max_tokens = modelConfig?.max_input_tokens || 200000; // Fallback to 200k
    
    // Recalculate usage_percentage (baseTokens already includes system instructions)
    const usage_percentage = new_max_tokens > 0 ? (state.baseTokens / new_max_tokens) * 100 : 0;
    
    set({
      totalTokens: state.baseTokens,
      maxTokens: new_max_tokens,
      usagePercentage: usage_percentage,
      modelName: model_name,
    });
  },
  clearContextUsage: () => set({
    totalTokens: 0,
    maxTokens: 0,
    usagePercentage: 0,
    modelName: null,
    sessionId: null,
    isVisible: false,
    baseTokens: 0,
  }),
  clear: () => set({
    totalTokens: 0,
    maxTokens: 0,
    usagePercentage: 0,
    modelName: null,
    sessionId: null,
    isVisible: false,
    baseTokens: 0,
  }),
}));

// Export clear function for store-utils
export const clearContextUsage = () => {
  useContextUsage.getState().clear();
};

