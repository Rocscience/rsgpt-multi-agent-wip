'use client';

import { create } from 'zustand';
import { ModelName } from '@/lib/types';

/**
 * Holds the first message typed on /chat so it appears immediately on /chat/[id].
 */
type PendingState = {
  text: string;
  sources: string[]; // knowledge base selections
  selectedModel?: ModelName; // selected model for the message
  set: (p: { text: string; sources: string[]; selectedModel?: ModelName }) => void;
  clear: () => void;
};

export const usePendingFirstMessage = create<PendingState>((set) => ({
  text: '',
  sources: [],
  selectedModel: undefined,
  set: (p) => set(p),
  clear: () => set({ text: '', sources: [], selectedModel: undefined }),
}));

// Export the store instance for clearing all stores on logout
export const clearPendingMessage = () => usePendingFirstMessage.getState().clear();
