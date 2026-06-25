'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

interface CitationHighlightContextType {
  highlightedUrl: string | null;
  setHighlightedUrl: (url: string | null) => void;
}

const CitationHighlightContext = createContext<CitationHighlightContextType | undefined>(undefined);

export function CitationHighlightProvider({ children }: { children: ReactNode }) {
  const [highlightedUrl, setHighlightedUrl] = useState<string | null>(null);

  return (
    <CitationHighlightContext.Provider value={{ highlightedUrl, setHighlightedUrl }}>
      {children}
    </CitationHighlightContext.Provider>
  );
}

export function useCitationHighlight() {
  const context = useContext(CitationHighlightContext);
  if (context === undefined) {
    throw new Error('useCitationHighlight must be used within a CitationHighlightProvider');
  }
  return context;
}
