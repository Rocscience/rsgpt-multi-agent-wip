'use client';

import { create } from 'zustand';

interface SourceResult {
  title?: string;
  url?: string;
  date?: string;
  lastUpdated?: string;
  snippet?: string;
  source?: string;
}

interface SourceListState {
  searchResults: SourceResult[];
  isLoading: boolean;
  isVisible: boolean;
  activeMessageId: string | null;
  setSearchResults: (results: SourceResult[]) => void;
  setLoading: (loading: boolean) => void;
  setVisible: (visible: boolean) => void;
  toggleVisible: () => void;
  clearSources: () => void;
  openSourcesForMessage: (messageId: string, results: SourceResult[]) => void;
}

// Helper function to deduplicate sources by URL
const deduplicateSources = (results: SourceResult[]): SourceResult[] => {
  const seen = new Set<string>();
  return results.filter(result => {
    if (!result.url || seen.has(result.url)) {
      return false;
    }
    seen.add(result.url);
    return true;
  });
};

export const useSourceList = create<SourceListState>((set) => ({
  searchResults: [],
  isLoading: false,
  isVisible: false,
  activeMessageId: null,
  setSearchResults: (results) => set({ searchResults: deduplicateSources(results) }),
  setLoading: (loading) => set({ isLoading: loading }),
  setVisible: (visible) => set((state) => ({ 
    isVisible: visible,
    activeMessageId: visible ? state.activeMessageId : null // Clear activeMessageId when closing
  })),
  toggleVisible: () => set((state) => ({ 
    isVisible: !state.isVisible,
    activeMessageId: state.isVisible ? null : state.activeMessageId // Clear activeMessageId when closing
  })),
  clearSources: () => set({ searchResults: [], isLoading: false, isVisible: false, activeMessageId: null }),
  openSourcesForMessage: (messageId: string, results: SourceResult[]) => set({ 
    searchResults: deduplicateSources(results), 
    isVisible: true,
    activeMessageId: messageId
  }),
}));
